using KrylovKit

struct FloquetEigenResult
    eigenvalue::ComplexF64
    subleading_eigenvalue::Union{Nothing,ComplexF64}
    spectral_gap::Float64
    right_vector::Vector{ComplexF64}
    left_vector::Vector{ComplexF64}
    right_residual::Float64
    left_residual::Float64
    iterations::Int
    matvec_count::Int
    backend::Symbol
    converged::Bool
    fallback_used::Bool
    nonconvergence_reason::Union{Nothing,Symbol}
end

struct FloquetWarmStart
    vector::Vector{ComplexF64}
    exact_dt_bits::String
    q_identity::String
    layout::AugmentedLayout
end

FloquetWarmStart(vector::AbstractVector, exact_dt::Real, q_identity::AbstractString,
                 layout::AugmentedLayout) =
    FloquetWarmStart(ComplexF64.(vector), bitstring(Float64(exact_dt)),
                     String(q_identity), layout)

function validate_warm_start(warm::FloquetWarmStart, exact_dt::Real,
                             q_identity::AbstractString, layout::AugmentedLayout)
    warm.exact_dt_bits == bitstring(Float64(exact_dt)) ||
        throw(ArgumentError("warm-start dt differs at the bit level"))
    warm.q_identity == q_identity ||
        throw(ArgumentError("warm-start q/cache identity does not match"))
    warm.layout.bond_dimension == layout.bond_dimension &&
        warm.layout.liouville_dimension == layout.liouville_dimension &&
        warm.layout.augmented_dimension == layout.augmented_dimension ||
        throw(ArgumentError("warm-start augmented layout does not match"))
    length(warm.vector) == layout.augmented_dimension ||
        throw(DimensionMismatch("warm-start vector has the wrong length"))
    return warm.vector
end

function _relative_residual(operator, vector, eigenvalue)
    applied = similar(vector)
    mul!(applied, operator, vector)
    return norm(applied .- eigenvalue .* vector) / norm(vector)
end

function _krylov_eigenpairs(floquet::FloquetOperator, initial::Vector{ComplexF64},
                            candidate_count::Int, tolerance::Real,
                            max_iterations::Int)
    n = size(floquet, 1)
    count = min(candidate_count, n - 1)
    count > 0 || throw(ArgumentError("augmented eigensolve needs dimension at least two"))
    krylov_dimension = min(n, max(count + 1, min(20, n)))
    forward = FloquetLinearOperator(floquet)
    forward_action = x -> forward * x
    values, vectors, right_info = KrylovKit.eigsolve(
        forward_action, initial, count, :LM;
        tol=tolerance, maxiter=max_iterations, krylovdim=krylov_dimension)
    isempty(values) && throw(ErrorException("Krylov solver returned no eigenpairs"))
    selected = argmin(abs.(values .- one(eltype(values))))
    λ = ComplexF64(values[selected])
    right = ComplexF64.(vectors[selected])

    # Use a distinct solver view because each view owns mutable, non-reentrant work.
    adjoint_view = adjoint(FloquetLinearOperator(floquet))
    adjoint_action = x -> adjoint_view * x
    left_values, left_vectors, left_info = KrylovKit.eigsolve(
        adjoint_action, copy(initial), count, :LM;
        tol=tolerance, maxiter=max_iterations, krylovdim=krylov_dimension)
    left_selected = argmin(abs.(left_values .- conj(λ)))
    left = ComplexF64.(left_vectors[left_selected])
    overlap = dot(left, right)
    abs(overlap) > sqrt(eps(Float64)) ||
        throw(ErrorException("left/right leading eigenvectors have vanishing overlap"))
    right ./= overlap

    other = [ComplexF64(values[i]) for i in eachindex(values) if i != selected]
    subleading = isempty(other) ? nothing : other[argmax(abs.(other))]
    gap = isnothing(subleading) ? NaN : abs(λ) - abs(subleading)
    right_residual = _relative_residual(FloquetLinearOperator(floquet), right, λ)
    left_residual = _relative_residual(
        adjoint(FloquetLinearOperator(floquet)), left, conj(λ))
    converged = right_info.converged >= count &&
        left_info.converged >= count &&
        right_residual <= tolerance && left_residual <= tolerance
    return FloquetEigenResult(
        λ, subleading, gap, right, left, right_residual, left_residual,
        right_info.numiter + left_info.numiter,
        right_info.numops + left_info.numops, :krylov, converged, false,
        converged ? nothing : :krylov_nonconvergence)
end

function _period_eigenvector(operator, initial::Vector{ComplexF64},
                             tolerance::Real, max_iterations::Int)
    current = copy(initial)
    norm(current) > 0 || throw(ArgumentError("initial vector must be nonzero"))
    current ./= norm(current)
    next = similar(current)
    λ = zero(ComplexF64)
    residual = Inf
    for iteration in 1:max_iterations
        mul!(next, operator, current)
        scale = norm(next)
        scale > 0 || throw(ErrorException("period iteration reached the zero vector"))
        next ./= scale
        mul!(current, operator, next)
        λ = dot(next, current)
        residual = norm(current .- λ .* next)
        current, next = next, current
        residual <= tolerance &&
            return current, λ, residual, iteration, 2iteration, true
    end
    return current, λ, residual, max_iterations, 2max_iterations, false
end

function _period_iteration(floquet::FloquetOperator, initial::Vector{ComplexF64},
                           tolerance::Real, max_iterations::Int)
    right, λ, right_residual, right_iterations, right_ops, right_ok =
        _period_eigenvector(FloquetLinearOperator(floquet), initial,
                            tolerance, max_iterations)
    left, left_λ, left_residual, left_iterations, left_ops, left_ok =
        _period_eigenvector(adjoint(FloquetLinearOperator(floquet)), initial,
                            tolerance, max_iterations)
    overlap = dot(left, right)
    abs(overlap) > sqrt(eps(Float64)) ||
        throw(ErrorException("fallback left/right eigenvectors have vanishing overlap"))
    right ./= overlap
    right_residual = _relative_residual(FloquetLinearOperator(floquet), right, λ)
    left_residual = _relative_residual(
        adjoint(FloquetLinearOperator(floquet)), left, left_λ)
    converged = right_ok && left_ok &&
        right_residual <= tolerance && left_residual <= tolerance
    return FloquetEigenResult(
        λ, nothing, NaN, right, left, right_residual, left_residual,
        right_iterations + left_iterations, right_ops + left_ops,
        :period_iteration, converged, true,
        converged ? nothing : :maximum_iterations)
end

function solve_floquet_steady_state(floquet::FloquetOperator;
        backend::Symbol=:krylov, candidate_count::Integer=4,
        tolerance::Real=1e-10, max_iterations::Integer=1000,
        initial_vector=nothing, warm_start::Union{Nothing,FloquetWarmStart}=nothing,
        exact_dt::Union{Nothing,Real}=nothing,
        q_identity::Union{Nothing,AbstractString}=nothing)
    tolerance > 0 || throw(ArgumentError("eigensolver tolerance must be positive"))
    max_iterations > 0 || throw(ArgumentError("maximum iterations must be positive"))
    candidate_count > 0 || throw(ArgumentError("candidate count must be positive"))
    backend in (:krylov, :period_iteration) ||
        throw(ArgumentError("unsupported Floquet eigensolver backend"))
    if !isnothing(warm_start)
        isnothing(exact_dt) && throw(ArgumentError("warm start requires exact_dt"))
        isnothing(q_identity) && throw(ArgumentError("warm start requires q_identity"))
        initial_vector = validate_warm_start(
            warm_start, exact_dt, q_identity, floquet.layout)
    end
    initial = isnothing(initial_vector) ?
        ones(ComplexF64, size(floquet, 1)) : ComplexF64.(initial_vector)
    length(initial) == size(floquet, 1) ||
        throw(DimensionMismatch("initial vector has the wrong augmented dimension"))
    norm(initial) > 0 || throw(ArgumentError("initial vector must be nonzero"))

    if backend === :period_iteration
        return _period_iteration(floquet, initial, tolerance, Int(max_iterations))
    end
    result = _krylov_eigenpairs(
        floquet, initial, Int(candidate_count), tolerance, Int(max_iterations))
    result.converged && return result
    fallback = _period_iteration(floquet, result.right_vector,
                                 tolerance, Int(max_iterations))
    return fallback
end

function reduce_system_state(augmented::AbstractVector, v_left::AbstractVector;
                             normalize::Bool=true)
    length(augmented) == 4length(v_left) ||
        throw(DimensionMismatch("augmented state and left boundary are incompatible"))
    system_vector = transpose(v_left) * reshape(augmented, length(v_left), 4)
    density = reshape(ComplexF64.(vec(system_vector)), 2, 2)
    raw_trace = tr(density)
    if normalize
        abs(raw_trace) > sqrt(eps(Float64)) ||
            throw(ArgumentError("cannot normalize a zero-trace reduced state"))
        density ./= raw_trace
    end
    hermiticity_error = norm(density - adjoint(density))
    hermitian_density = Hermitian((density + adjoint(density)) / 2)
    minimum_eigenvalue = minimum(real.(eigvals(hermitian_density)))
    return (; density_matrix=density, trace=raw_trace,
            hermiticity_error, minimum_eigenvalue)
end

reduce_system_state(augmented::AbstractVector, adapter::UniformIFAdapter;
                    normalize::Bool=true) =
    reduce_system_state(augmented, adapter.v_left; normalize)

function micromotion_states(floquet::FloquetOperator, initial::AbstractVector,
                            v_left::AbstractVector, model::SpinBosonModel;
                            omega_d::Real, exact_dt::Real)
    length(initial) == size(floquet, 1) ||
        throw(DimensionMismatch("micromotion initial state has the wrong dimension"))
    period_steps = length(floquet.left_channels)
    phase_states = Vector{Vector{ComplexF64}}(undef, period_steps + 1)
    phase_states[1] = ComplexF64.(initial)
    work = StepWorkspace(floquet)
    for phase in 1:period_steps
        phase_states[phase + 1] = similar(phase_states[1])
        _apply_phase!(phase_states[phase + 1], phase_states[phase],
                      floquet, phase, work)
    end
    reduced = [reduce_system_state(state, v_left).density_matrix
               for state in phase_states]
    sigma_y = ComplexF64[0 -im; im 0]
    σx = [real(tr(SIGMA_X * rho)) for rho in reduced]
    σy = [real(tr(sigma_y * rho)) for rho in reduced]
    σz = [real(tr(SIGMA_Z * rho)) for rho in reduced]
    energies = Float64[]
    powers = Float64[]
    drive_axis = model.drive === :longitudinal ? SIGMA_X : SIGMA_Z
    for index in eachindex(reduced)
        time = (index - 1) * exact_dt
        push!(energies, real(tr(system_hamiltonian(model, time, omega_d) *
                                reduced[index])))
        derivative = -model.epsilon_d * omega_d * sin(omega_d * time) * drive_axis
        push!(powers, real(tr(derivative * reduced[index])))
    end
    augmented_closure = norm(phase_states[end] - phase_states[1]) /
        max(norm(phase_states[1]), eps(Float64))
    reduced_closure = norm(reduced[end] - reduced[1])
    return (; phase_states, rho_system=reduced, sigma_x=σx, sigma_y=σy,
            sigma_z=σz, system_energy=energies, drive_power=powers,
            augmented_closure, reduced_closure)
end
