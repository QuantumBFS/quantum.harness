function normalized_singular_values(values::AbstractVector)
    normalization = norm(values)
    normalization > 0 || error("two-site update produced a zero state")
    return collect(real(values ./ normalization)), normalization
end

function update_horizontal_bond!(
    state::DenseFinitePEPSGammaLambda,
    x::Int,
    y::Int,
    max_bond_dimension::Int,
    gate::Array{<:Number,4},
)
    left = state[x, y]
    right = state[x + 1, y]
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
    left_dims = size(theta)[1:4]
    right_dims = size(theta)[5:8]
    factorization = svd(reshape(theta, prod(left_dims), prod(right_dims)))
    kept = min(max_bond_dimension, length(factorization.S))
    discarded = sum(abs2, @view factorization.S[(kept + 1):end])
    total = sum(abs2, factorization.S)
    truncation_error = total == 0 ? 0.0 : discarded / total
    singular_values, normalization = normalized_singular_values(@view factorization.S[1:kept])

    new_left = reshape(@view(factorization.U[:, 1:kept]), left_dims..., kept)
    new_left = permutedims(new_left, (1, 2, 4, 5, 3))
    new_left = remove_leg_weight(new_left, left.left, 1)
    new_left = remove_leg_weight(new_left, left.top, 2)
    new_left = remove_leg_weight(new_left, left.bottom, 5)

    new_right = reshape(@view(factorization.Vt[1:kept, :]), kept, right_dims...)
    new_right = permutedims(new_right, (1, 3, 2, 4, 5))
    new_right = remove_leg_weight(new_right, right.top, 2)
    new_right = remove_leg_weight(new_right, right.right, 4)
    new_right = remove_leg_weight(new_right, right.bottom, 5)

    left.gamma = Array(new_left)
    right.gamma = Array(new_right)
    left.right = singular_values
    right.left = singular_values
    return truncation_error, normalization
end

function update_vertical_bond!(
    state::DenseFinitePEPSGammaLambda,
    x::Int,
    y::Int,
    max_bond_dimension::Int,
    gate::Array{<:Number,4},
)
    upper = state[x, y]
    lower = state[x, y + 1]
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
    left_dims = size(theta)[1:4]
    right_dims = size(theta)[5:8]
    factorization = svd(reshape(theta, prod(left_dims), prod(right_dims)))
    kept = min(max_bond_dimension, length(factorization.S))
    discarded = sum(abs2, @view factorization.S[(kept + 1):end])
    total = sum(abs2, factorization.S)
    truncation_error = total == 0 ? 0.0 : discarded / total
    singular_values, normalization = normalized_singular_values(@view factorization.S[1:kept])

    new_upper = reshape(@view(factorization.U[:, 1:kept]), left_dims..., kept)
    new_upper = permutedims(new_upper, (1, 2, 4, 3, 5))
    new_upper = remove_leg_weight(new_upper, upper.left, 1)
    new_upper = remove_leg_weight(new_upper, upper.top, 2)
    new_upper = remove_leg_weight(new_upper, upper.right, 4)

    new_lower = reshape(@view(factorization.Vt[1:kept, :]), kept, right_dims...)
    new_lower = permutedims(new_lower, (3, 1, 2, 4, 5))
    new_lower = remove_leg_weight(new_lower, lower.left, 1)
    new_lower = remove_leg_weight(new_lower, lower.right, 4)
    new_lower = remove_leg_weight(new_lower, lower.bottom, 5)

    upper.gamma = Array(new_upper)
    lower.gamma = Array(new_lower)
    upper.bottom = singular_values
    lower.top = singular_values
    return truncation_error, normalization
end

function apply_trotter_step!(
    state::DenseFinitePEPSGammaLambda,
    delta::Real,
    para::AbstractDict,
)
    order = get(para, :TrotterOrder, 2)
    order in (1, 2) || throw(ArgumentError("TrotterOrder must be 1 or 2"))
    D = para[:D]
    gate_delta = order == 1 ? delta : delta / 2
    horizontal_gates = [
        trotter_gate(state.Lx, state.Ly, x, y, :right, gate_delta, para)
        for x in 1:(state.Lx - 1), y in 1:state.Ly
    ]
    vertical_gates = [
        trotter_gate(state.Lx, state.Ly, x, y, :down, gate_delta, para)
        for x in 1:state.Lx, y in 1:(state.Ly - 1)
    ]
    max_error = 0.0
    log_normalization = 0.0
    for y in 1:state.Ly, x in 1:(state.Lx - 1)
        error, normalization = update_horizontal_bond!(state, x, y, D, horizontal_gates[x, y])
        max_error = max(max_error, error)
        log_normalization += log(normalization)
    end
    for x in 1:state.Lx, y in 1:(state.Ly - 1)
        error, normalization = update_vertical_bond!(state, x, y, D, vertical_gates[x, y])
        max_error = max(max_error, error)
        log_normalization += log(normalization)
    end
    if order == 2
        for x in state.Lx:-1:1, y in (state.Ly - 1):-1:1
            error, normalization = update_vertical_bond!(state, x, y, D, vertical_gates[x, y])
            max_error = max(max_error, error)
            log_normalization += log(normalization)
        end
        for y in state.Ly:-1:1, x in (state.Lx - 1):-1:1
            error, normalization = update_horizontal_bond!(state, x, y, D, horizontal_gates[x, y])
            max_error = max(max_error, error)
            log_normalization += log(normalization)
        end
    end
    return (; max_truncation_error=max_error, log_normalization)
end

function imaginary_time_evolve!(state::DenseFinitePEPSGammaLambda, para::AbstractDict)
    beta = para[:beta]
    beta >= 0 || throw(ArgumentError("beta must be nonnegative"))
    target_time = beta / 2
    target_time == 0 && return NamedTuple[]
    requested_tau = para[:tau]
    requested_tau > 0 || throw(ArgumentError("tau must be positive"))
    steps = max(1, ceil(Int, target_time / requested_tau))
    delta = target_time / steps
    history = NamedTuple[]
    for step in 1:steps
        update = apply_trotter_step!(state, delta, para)
        push!(history, (; step, steps, delta, update...))
        if get(para, :verbose, 1) > 1
            println("METTS SU step $step/$steps, delta=$delta, max_error=$(update.max_truncation_error)")
        end
    end
    return history
end
