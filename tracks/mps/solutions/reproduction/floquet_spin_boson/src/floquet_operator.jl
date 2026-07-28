using LinearAlgebra

"""
One-period operator on the full `4χ` augmented state.

`q_storage` owns exactly one process-tensor kernel. `q_matrix` is a reshape
view of that same storage; only the two local channels vary with phase.
"""
struct FloquetOperator{T<:Number,Q<:Array{T,4},QM<:AbstractMatrix{T}}
    layout::AugmentedLayout
    q_storage::Q
    q_matrix::QM
    left_channels::Vector{Matrix{T}}
    right_channels::Vector{Matrix{T}}
end

function FloquetOperator(q::AbstractArray{<:Number,4},
                         left_channels::AbstractVector{<:AbstractMatrix},
                         right_channels::AbstractVector{<:AbstractMatrix})
    length(left_channels) == length(right_channels) ||
        throw(DimensionMismatch("left and right channel counts must agree"))
    isempty(left_channels) &&
        throw(ArgumentError("a Floquet period must contain at least one phase"))
    χ = size(q, 1)
    size(q) == (χ, 4, χ, 4) ||
        throw(DimensionMismatch("q must have shape (χ, 4, χ, 4)"))
    all(channel -> size(channel) == (4, 4), left_channels) ||
        throw(DimensionMismatch("every left half-step channel must be 4×4"))
    all(channel -> size(channel) == (4, 4), right_channels) ||
        throw(DimensionMismatch("every right half-step channel must be 4×4"))
    T = promote_type(eltype(q), mapreduce(eltype, promote_type, left_channels),
                     mapreduce(eltype, promote_type, right_channels))
    q_storage = Array{T,4}(q)
    q_matrix = reshape(q_storage, 4χ, 4χ)
    left = Matrix{T}.(left_channels)
    right = Matrix{T}.(right_channels)
    return FloquetOperator(AugmentedLayout(χ), q_storage, q_matrix, left, right)
end

@inline function _spin_unitary(model::SpinBosonModel, time::Real, omega_d::Real,
                               duration::Real)
    drive = model.epsilon_d * cos(omega_d * time)
    hx = model.omega / 2 + (model.drive === :longitudinal ? drive : 0.0)
    hz = model.drive === :transversal ? drive : 0.0
    radius = hypot(hx, hz)
    phase = radius * duration
    if iszero(radius)
        return Matrix{ComplexF64}(I, 2, 2)
    end
    scale = -im * sin(phase) / radius
    return ComplexF64[cos(phase) + scale * hz scale * hx;
                      scale * hx cos(phase) - scale * hz]
end

@inline _liouville_channel(unitary) = kron(transpose(conj(unitary)), unitary)

"""
Precompute both midpoint half-step channels for every phase of one exact period.
"""
function precompute_half_step_channels(model::SpinBosonModel, omega_d::Real,
                                       period_steps::Integer, exact_dt::Real)
    omega_d > 0 || throw(ArgumentError("drive frequency must be positive"))
    period_steps > 0 || throw(ArgumentError("period step count must be positive"))
    exact_dt > 0 || throw(ArgumentError("exact dt must be positive"))
    period = 2π / omega_d
    isapprox(period_steps * exact_dt, period; rtol=0, atol=64eps(period)) ||
        throw(ArgumentError("one Floquet period must contain exactly M time steps"))
    left = Vector{Matrix{ComplexF64}}(undef, period_steps)
    right = similar(left)
    half_dt = exact_dt / 2
    for phase_index in 1:period_steps
        start_time = (phase_index - 1) * exact_dt
        left_unitary = _spin_unitary(model, start_time + exact_dt / 4,
                                     omega_d, half_dt)
        right_unitary = _spin_unitary(model, start_time + 3exact_dt / 4,
                                      omega_d, half_dt)
        left[phase_index] = _liouville_channel(left_unitary)
        right[phase_index] = _liouville_channel(right_unitary)
    end
    return left, right
end

function FloquetOperator(adapter::UniformIFAdapter, model::SpinBosonModel,
                         omega_d::Real, period_steps::Integer, exact_dt::Real)
    bitstring(Float64(exact_dt)) == adapter.metadata["exact_dt_bits"] ||
        throw(ArgumentError("Floquet dt does not match the uniform-IF cache"))
    left, right = precompute_half_step_channels(model, omega_d, period_steps, exact_dt)
    return FloquetOperator(adapter.q, left, right)
end

StepWorkspace(floquet::FloquetOperator{T}) where {T} =
    StepWorkspace(floquet.layout, T)

Base.size(floquet::FloquetOperator) =
    (floquet.layout.augmented_dimension, floquet.layout.augmented_dimension)
Base.size(floquet::FloquetOperator, dimension::Integer) = size(floquet)[dimension]
Base.eltype(::FloquetOperator{T}) where {T} = T

@inline function _apply_phase!(y, x, floquet::FloquetOperator, phase::Int,
                               work::StepWorkspace)
    _apply_system_channel!(work.tmp1, x, floquet.left_channels[phase], floquet.layout)
    mul!(work.tmp2, floquet.q_matrix, work.tmp1)
    _apply_system_channel!(y, work.tmp2, floquet.right_channels[phase], floquet.layout)
    return y
end

@inline function _apply_phase_adjoint!(y, x, floquet::FloquetOperator, phase::Int,
                                       work::StepWorkspace)
    _apply_system_channel!(work.tmp1, x, adjoint(floquet.right_channels[phase]),
                           floquet.layout)
    mul!(work.tmp2, adjoint(floquet.q_matrix), work.tmp1)
    _apply_system_channel!(y, work.tmp2, adjoint(floquet.left_channels[phase]),
                           floquet.layout)
    return y
end

function apply_period!(y::AbstractVector, x::AbstractVector, floquet::FloquetOperator,
                       work::StepWorkspace)
    _check_augmented_vectors(y, x, floquet.layout)
    _check_workspace(work, floquet.layout)
    copyto!(work.period1, x)
    source = work.period1
    destination = work.period2
    for phase in eachindex(floquet.left_channels)
        _apply_phase!(destination, source, floquet, phase, work)
        source, destination = destination, source
    end
    copyto!(y, source)
    return y
end

function apply_period_adjoint!(y::AbstractVector, x::AbstractVector,
                               floquet::FloquetOperator, work::StepWorkspace)
    _check_augmented_vectors(y, x, floquet.layout)
    _check_workspace(work, floquet.layout)
    copyto!(work.period1, x)
    source = work.period1
    destination = work.period2
    for phase in length(floquet.left_channels):-1:1
        _apply_phase_adjoint!(destination, source, floquet, phase, work)
        source, destination = destination, source
    end
    copyto!(y, source)
    return y
end

estimated_dense_bytes(floquet::FloquetOperator) =
    size(floquet, 1)^2 * sizeof(eltype(floquet))

function dense_floquet(floquet::FloquetOperator; memory_limit_bytes::Integer)
    required = estimated_dense_bytes(floquet)
    required <= memory_limit_bytes ||
        throw(ArgumentError("dense QF requires $required bytes, above limit $memory_limit_bytes"))
    n = size(floquet, 1)
    dense = Matrix{eltype(floquet)}(undef, n, n)
    basis = zeros(eltype(floquet), n)
    work = StepWorkspace(floquet)
    for column in 1:n
        fill!(basis, 0)
        basis[column] = 1
        apply_period!(view(dense, :, column), basis, floquet, work)
    end
    return dense
end

LinearAlgebra.mul!(y::AbstractVector, floquet::FloquetOperator, x::AbstractVector) =
    apply_period!(y, x, floquet, StepWorkspace(floquet))

function Base.:*(floquet::FloquetOperator, x::AbstractVector)
    y = similar(x, promote_type(eltype(floquet), eltype(x)), size(floquet, 1))
    return mul!(y, floquet, x)
end

struct AdjointFloquetOperator{F<:FloquetOperator}
    parent::F
end

Base.adjoint(floquet::FloquetOperator) = AdjointFloquetOperator(floquet)
Base.size(operator::AdjointFloquetOperator) = reverse(size(operator.parent))
Base.eltype(operator::AdjointFloquetOperator) = eltype(operator.parent)

function LinearAlgebra.mul!(y::AbstractVector, operator::AdjointFloquetOperator,
                            x::AbstractVector)
    return apply_period_adjoint!(y, x, operator.parent, StepWorkspace(operator.parent))
end

function Base.:*(operator::AdjointFloquetOperator, x::AbstractVector)
    y = similar(x, promote_type(eltype(operator), eltype(x)), size(operator, 1))
    return mul!(y, operator, x)
end
