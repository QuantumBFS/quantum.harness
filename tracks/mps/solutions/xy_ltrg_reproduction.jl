module XYLTRGReproduction

using LinearAlgebra
using ITensors
using JSON
using QuadGK

export LTRGState,
    bilayer_step!,
    bond_hamiltonian,
    direct_bond_energies,
    exact_thermo,
    finite_difference_uniform,
    identity_state,
    log_partition_per_site,
    main,
    parse_cli,
    purification_bond_energies,
    run_bilayer_cell!,
    run_bilayer_curve,
    run_cell!,
    run_curve,
    run_negative_control,
    step!,
    vectorized_gate

const LOCAL_DIM = 2
const OPERATOR_DIM = LOCAL_DIM^2
const DIRECT_ENDPOINT_SAMPLES = 9

mutable struct LTRGState
    gamma_a::Array{Float64,3}
    gamma_b::Array{Float64,3}
    lambda_ab::Vector{Float64}
    lambda_ba::Vector{Float64}
    log_scale::Float64
    beta::Float64
end

pair_index(first::Int, second::Int) = (first - 1) * LOCAL_DIM + second
operator_index(bra::Int, ket::Int) = bra + LOCAL_DIM * (ket - 1)
operator_pair_index(first::Int, second::Int) = first + OPERATOR_DIM * (second - 1)

function bond_hamiltonian(
    J::Float64 = 1.0;
    pauli_convention::Bool = false,
)::Matrix{Float64}
    scale = pauli_convention ? 4.0 : 1.0
    h = zeros(Float64, LOCAL_DIM^2, LOCAL_DIM^2)
    h[2, 3] = -0.5 * J * scale
    h[3, 2] = -0.5 * J * scale
    return h
end

function vectorized_gate(
    tau::Float64,
    J::Float64 = 1.0;
    pauli_convention::Bool = false,
)::Matrix{Float64}
    tau > 0 || throw(ArgumentError("tau must be positive"))
    local_gate = exp(-tau * bond_hamiltonian(J; pauli_convention))
    return lift_bra_operator(local_gate)
end

function lift_bra_operator(local_operator::Matrix{Float64})::Matrix{Float64}
    size(local_operator) == (LOCAL_DIM^2, LOCAL_DIM^2) ||
        throw(DimensionMismatch("two-site operator dimension"))
    lifted = zeros(Float64, OPERATOR_DIM^2, OPERATOR_DIM^2)

    for ket1 in 1:LOCAL_DIM, ket2 in 1:LOCAL_DIM
        for bra1_in in 1:LOCAL_DIM, bra2_in in 1:LOCAL_DIM
            p1_in = operator_index(bra1_in, ket1)
            p2_in = operator_index(bra2_in, ket2)
            input = operator_pair_index(p1_in, p2_in)
            bra_in = pair_index(bra1_in, bra2_in)

            for bra1_out in 1:LOCAL_DIM, bra2_out in 1:LOCAL_DIM
                p1_out = operator_index(bra1_out, ket1)
                p2_out = operator_index(bra2_out, ket2)
                output = operator_pair_index(p1_out, p2_out)
                bra_out = pair_index(bra1_out, bra2_out)
                lifted[output, input] = local_operator[bra_out, bra_in]
            end
        end
    end
    return lifted
end

log2cosh(x::Float64) = abs(x) + log1p(exp(-2 * abs(x)))

function sech2(x::Float64)
    y = exp(-2 * abs(x))
    return 4 * y / (1 + y)^2
end

function exact_thermo(beta::Float64, J::Float64 = 1.0)::NamedTuple
    beta > 0 || throw(ArgumentError("beta must be positive"))

    log_integral, = quadgk(
        k -> log2cosh(0.5 * beta * J * cos(k)),
        0.0,
        pi;
        rtol = 1e-11,
    )
    energy_integral, = quadgk(
        k -> J * cos(k) * tanh(0.5 * beta * J * cos(k)),
        0.0,
        pi;
        rtol = 1e-11,
    )
    heat_integral, = quadgk(
        k -> (J * cos(k))^2 * sech2(0.5 * beta * J * cos(k)),
        0.0,
        pi;
        rtol = 1e-11,
    )

    return (
        free_energy = -log_integral / (pi * beta),
        energy = -energy_integral / (2 * pi),
        specific_heat = beta^2 * heat_integral / (4 * pi),
    )
end

function identity_state()::LTRGState
    gamma_a = zeros(Float64, 1, OPERATOR_DIM, 1)
    gamma_b = zeros(Float64, 1, OPERATOR_DIM, 1)
    for spin in 1:LOCAL_DIM
        physical = operator_index(spin, spin)
        gamma_a[1, physical, 1] = 1.0
        gamma_b[1, physical, 1] = 1.0
    end
    return LTRGState(gamma_a, gamma_b, [1.0], [1.0], 0.0, 0.0)
end

function safe_inverse(values::Vector{Float64})
    threshold = eps(Float64) * maximum(abs, values)
    return map(value -> abs(value) > threshold ? inv(value) : 0.0, values)
end

function update_bond(
    gamma_left::Array{Float64,3},
    lambda_center::Vector{Float64},
    gamma_right::Array{Float64,3},
    lambda_outer::Vector{Float64},
    gate::Matrix{Float64},
    Dc::Int;
    cutoff::Float64 = 0.0,
)::NamedTuple
    outer_left, physical_left, center_left = size(gamma_left)
    center_right, physical_right, outer_right = size(gamma_right)
    physical_left == OPERATOR_DIM || throw(DimensionMismatch("left physical dimension"))
    physical_right == OPERATOR_DIM || throw(DimensionMismatch("right physical dimension"))
    center_left == center_right == length(lambda_center) ||
        throw(DimensionMismatch("center bond dimension"))
    outer_left == outer_right == length(lambda_outer) ||
        throw(DimensionMismatch("outer bond dimension"))
    size(gate) == (OPERATOR_DIM^2, OPERATOR_DIM^2) ||
        throw(DimensionMismatch("two-site gate dimension"))
    Dc > 0 || throw(ArgumentError("Dc must be positive"))

    left = gamma_left .* reshape(lambda_outer, outer_left, 1, 1)
    left .*= reshape(lambda_center, 1, 1, center_left)
    right = gamma_right .* reshape(lambda_outer, 1, 1, outer_right)

    theta_matrix =
        reshape(left, outer_left * OPERATOR_DIM, center_left) *
        reshape(right, center_right, OPERATOR_DIM * outer_right)
    theta = reshape(
        gate * reshape(
            permutedims(
                reshape(
                    theta_matrix,
                    outer_left,
                    OPERATOR_DIM,
                    OPERATOR_DIM,
                    outer_right,
                ),
                (2, 3, 1, 4),
            ),
            OPERATOR_DIM^2,
            outer_left * outer_right,
        ),
        OPERATOR_DIM,
        OPERATOR_DIM,
        outer_left,
        outer_right,
    )
    theta = permutedims(theta, (3, 1, 2, 4))

    left_index = Index(outer_left, "Outer,left")
    left_physical = Index(OPERATOR_DIM, "Physical,left")
    right_physical = Index(OPERATOR_DIM, "Physical,right")
    right_index = Index(outer_right, "Outer,right")
    theta_tensor = ITensor(
        theta,
        left_index,
        left_physical,
        right_physical,
        right_index,
    )
    factorization = svd(
        theta_tensor,
        left_index,
        left_physical;
        maxdim = Dc,
        cutoff = cutoff,
    )

    kept = dim(factorization.u)
    singular_values = [
        factorization.S[factorization.u => index, factorization.v => index] for
        index in 1:kept
    ]
    normalization = maximum(singular_values)
    normalization > 0 || error("LTRG update produced a zero singular spectrum")

    left_isometry = Array(
        factorization.U,
        left_index,
        left_physical,
        factorization.u,
    )
    right_isometry = Array(
        factorization.V,
        factorization.v,
        right_physical,
        right_index,
    )
    inverse_outer = safe_inverse(lambda_outer)
    gamma_left_new = left_isometry .* reshape(inverse_outer, outer_left, 1, 1)
    gamma_right_new = right_isometry .* reshape(inverse_outer, 1, 1, outer_right)

    return (
        gamma_left = gamma_left_new,
        gamma_right = gamma_right_new,
        lambda = singular_values ./ normalization,
        log_norm = log(normalization),
        truncerr = Float64(factorization.spec.truncerr),
        kept = kept,
    )
end

function step!(
    state::LTRGState,
    gate::Matrix{Float64},
    tau::Float64,
    Dc::Int;
    cutoff::Float64 = 0.0,
)::NamedTuple
    tau > 0 || throw(ArgumentError("tau must be positive"))

    ab = update_bond(
        state.gamma_a,
        state.lambda_ab,
        state.gamma_b,
        state.lambda_ba,
        gate,
        Dc;
        cutoff,
    )
    state.gamma_a = ab.gamma_left
    state.gamma_b = ab.gamma_right
    state.lambda_ab = ab.lambda
    state.log_scale += 0.5 * ab.log_norm

    ba = update_bond(
        state.gamma_b,
        state.lambda_ba,
        state.gamma_a,
        state.lambda_ab,
        gate,
        Dc;
        cutoff,
    )
    state.gamma_b = ba.gamma_left
    state.gamma_a = ba.gamma_right
    state.lambda_ba = ba.lambda
    state.log_scale += 0.5 * ba.log_norm
    state.beta += tau

    return (
        log_norm_ab = ab.log_norm,
        log_norm_ba = ba.log_norm,
        truncerr_ab = ab.truncerr,
        truncerr_ba = ba.truncerr,
        kept_ab = ab.kept,
        kept_ba = ba.kept,
    )
end

function bilayer_step!(
    state::LTRGState,
    quarter_gate::Matrix{Float64},
    half_gate::Matrix{Float64},
    tau::Float64,
    Dc::Int;
    cutoff::Float64 = 0.0,
)::NamedTuple
    tau > 0 || throw(ArgumentError("tau must be positive"))

    ab_first = update_bond(
        state.gamma_a,
        state.lambda_ab,
        state.gamma_b,
        state.lambda_ba,
        quarter_gate,
        Dc;
        cutoff,
    )
    state.gamma_a = ab_first.gamma_left
    state.gamma_b = ab_first.gamma_right
    state.lambda_ab = ab_first.lambda
    state.log_scale += 0.5 * ab_first.log_norm

    ba = update_bond(
        state.gamma_b,
        state.lambda_ba,
        state.gamma_a,
        state.lambda_ab,
        half_gate,
        Dc;
        cutoff,
    )
    state.gamma_b = ba.gamma_left
    state.gamma_a = ba.gamma_right
    state.lambda_ba = ba.lambda
    state.log_scale += 0.5 * ba.log_norm

    ab_second = update_bond(
        state.gamma_a,
        state.lambda_ab,
        state.gamma_b,
        state.lambda_ba,
        quarter_gate,
        Dc;
        cutoff,
    )
    state.gamma_a = ab_second.gamma_left
    state.gamma_b = ab_second.gamma_right
    state.lambda_ab = ab_second.lambda
    state.log_scale += 0.5 * ab_second.log_norm
    state.beta += tau

    return (
        log_norm_ab = ab_first.log_norm + ab_second.log_norm,
        log_norm_ba = ba.log_norm,
        truncerr_ab = max(ab_first.truncerr, ab_second.truncerr),
        truncerr_ba = ba.truncerr,
        truncerr_total =
            ab_first.truncerr + ba.truncerr + ab_second.truncerr,
        max_truncerr = max(
            ab_first.truncerr,
            ba.truncerr,
            ab_second.truncerr,
        ),
        kept_ab = ab_second.kept,
        kept_ba = ba.kept,
    )
end

function log_partition_per_site(state::LTRGState)::Float64
    dim_ba, physical_a, dim_ab = size(state.gamma_a)
    dim_ab_b, physical_b, dim_ba_b = size(state.gamma_b)
    dim_ab == dim_ab_b == length(state.lambda_ab) ||
        throw(DimensionMismatch("AB bond dimension"))
    dim_ba == dim_ba_b == length(state.lambda_ba) ||
        throw(DimensionMismatch("BA bond dimension"))
    physical_a == physical_b == OPERATOR_DIM ||
        throw(DimensionMismatch("physical dimension"))

    trace_a = zeros(Float64, dim_ba, dim_ab)
    trace_b = zeros(Float64, dim_ab, dim_ba)
    for spin in 1:LOCAL_DIM
        physical = operator_index(spin, spin)
        trace_a .+= state.gamma_a[:, physical, :]
        trace_b .+= state.gamma_b[:, physical, :]
    end
    trace_a .*= reshape(state.lambda_ba, dim_ba, 1)
    trace_b .*= reshape(state.lambda_ab, dim_ab, 1)

    cell_eigenvalues = eigvals(trace_a * trace_b)
    spectral_radius = maximum(abs, cell_eigenvalues)
    spectral_radius > 0 || error("trace transfer matrix has zero spectral radius")
    return state.log_scale + 0.5 * log(spectral_radius)
end

function traced_site_matrix(
    gamma::Array{Float64,3},
    lambda_in::Vector{Float64},
)::Matrix{Float64}
    incoming, physical_dimension, outgoing = size(gamma)
    incoming == length(lambda_in) || throw(DimensionMismatch("incoming bond dimension"))
    physical_dimension == OPERATOR_DIM || throw(DimensionMismatch("physical dimension"))

    traced = zeros(Float64, incoming, outgoing)
    for spin in 1:LOCAL_DIM
        traced .+= gamma[:, operator_index(spin, spin), :]
    end
    traced .*= reshape(lambda_in, incoming, 1)
    return traced
end

function bond_insertion_matrix(
    gamma_left::Array{Float64,3},
    lambda_center::Vector{Float64},
    gamma_right::Array{Float64,3},
    lambda_outer::Vector{Float64},
    operator::Matrix{Float64},
)::Matrix{Float64}
    outer_left, physical_left, center_left = size(gamma_left)
    center_right, physical_right, outer_right = size(gamma_right)
    outer_left == outer_right == length(lambda_outer) ||
        throw(DimensionMismatch("outer bond dimension"))
    center_left == center_right == length(lambda_center) ||
        throw(DimensionMismatch("center bond dimension"))
    physical_left == physical_right == OPERATOR_DIM ||
        throw(DimensionMismatch("physical dimension"))
    size(operator) == (LOCAL_DIM^2, LOCAL_DIM^2) ||
        throw(DimensionMismatch("two-site operator dimension"))

    insertion = zeros(Float64, outer_left, outer_right)
    for bra_left in 1:LOCAL_DIM, bra_right in 1:LOCAL_DIM
        bra_pair = pair_index(bra_left, bra_right)
        for ket_left in 1:LOCAL_DIM, ket_right in 1:LOCAL_DIM
            ket_pair = pair_index(ket_left, ket_right)
            weight = operator[ket_pair, bra_pair]
            iszero(weight) && continue

            physical_left_index = operator_index(bra_left, ket_left)
            physical_right_index = operator_index(bra_right, ket_right)
            left = gamma_left[:, physical_left_index, :] .*
                   reshape(lambda_outer, outer_left, 1)
            right = gamma_right[:, physical_right_index, :] .*
                    reshape(lambda_center, center_right, 1)
            insertion .+= weight .* (left * right)
        end
    end
    return insertion
end

function dominant_insertion_expectation(
    transfer::Matrix{Float64},
    insertion::Matrix{Float64},
)::Float64
    size(transfer, 1) == size(transfer, 2) ||
        throw(DimensionMismatch("transfer matrix must be square"))
    size(insertion) == size(transfer) ||
        throw(DimensionMismatch("insertion and transfer dimensions"))

    right_system = eigen(transfer)
    right_index = argmax(abs.(right_system.values))
    eigenvalue = right_system.values[right_index]
    right = right_system.vectors[:, right_index]

    left_system = eigen(transpose(transfer))
    left_index = argmin(abs.(left_system.values .- eigenvalue))
    left_eigenvalue = left_system.values[left_index]
    left = left_system.vectors[:, left_index]
    eigen_tolerance = 1e-10 * max(1.0, abs(eigenvalue))
    abs(left_eigenvalue - eigenvalue) <= eigen_tolerance ||
        error("left and right dominant transfer eigenvalues do not match")

    overlap = sum(left .* right)
    abs(overlap) > 100 * eps(Float64) * norm(left) * norm(right) ||
        error("dominant transfer eigenvectors have zero overlap")
    expectation = sum(left .* (insertion * right)) / (eigenvalue * overlap)
    imaginary_tolerance = 1e-10 * max(1.0, abs(real(expectation)))
    abs(imag(expectation)) <= imaginary_tolerance ||
        error("bond expectation has a non-negligible imaginary part")
    return Float64(real(expectation))
end

function direct_bond_energies(
    state::LTRGState,
    J::Float64 = 1.0;
    pauli_convention::Bool = false,
)::NamedTuple
    trace_a = traced_site_matrix(state.gamma_a, state.lambda_ba)
    trace_b = traced_site_matrix(state.gamma_b, state.lambda_ab)
    h = bond_hamiltonian(J; pauli_convention)

    insertion_ab = bond_insertion_matrix(
        state.gamma_a,
        state.lambda_ab,
        state.gamma_b,
        state.lambda_ba,
        h,
    )
    insertion_ba = bond_insertion_matrix(
        state.gamma_b,
        state.lambda_ba,
        state.gamma_a,
        state.lambda_ab,
        h,
    )
    energy_ab = dominant_insertion_expectation(trace_a * trace_b, insertion_ab)
    energy_ba = dominant_insertion_expectation(trace_b * trace_a, insertion_ba)
    return (ab = energy_ab, ba = energy_ba, mean = 0.5 * (energy_ab + energy_ba))
end

function purification_bond_expectation(
    gamma_left::Array{Float64,3},
    lambda_center::Vector{Float64},
    gamma_right::Array{Float64,3},
    lambda_outer::Vector{Float64},
    operator::Matrix{Float64},
)::Float64
    outer_left, physical_left, center_left = size(gamma_left)
    center_right, physical_right, outer_right = size(gamma_right)
    outer_left == outer_right == length(lambda_outer) ||
        throw(DimensionMismatch("outer bond dimension"))
    center_left == center_right == length(lambda_center) ||
        throw(DimensionMismatch("center bond dimension"))
    physical_left == physical_right == OPERATOR_DIM ||
        throw(DimensionMismatch("physical dimension"))

    left = gamma_left .* reshape(lambda_outer, outer_left, 1, 1)
    left .*= reshape(lambda_center, 1, 1, center_left)
    right = gamma_right .* reshape(lambda_outer, 1, 1, outer_right)
    theta_matrix =
        reshape(left, outer_left * OPERATOR_DIM, center_left) *
        reshape(right, center_right, OPERATOR_DIM * outer_right)
    theta = reshape(
        theta_matrix,
        outer_left,
        OPERATOR_DIM,
        OPERATOR_DIM,
        outer_right,
    )
    physical_theta = reshape(
        permutedims(theta, (2, 3, 1, 4)),
        OPERATOR_DIM^2,
        outer_left * outer_right,
    )
    lifted_operator = lift_bra_operator(operator)
    norm_squared = sum(abs2, physical_theta)
    norm_squared > 0 || error("purification two-site wavefunction has zero norm")
    expectation = sum(physical_theta .* (lifted_operator * physical_theta)) / norm_squared
    return Float64(expectation)
end

function purification_bond_energies(
    state::LTRGState,
    J::Float64 = 1.0;
    pauli_convention::Bool = false,
)::NamedTuple
    h = bond_hamiltonian(J; pauli_convention)
    energy_ab = purification_bond_expectation(
        state.gamma_a,
        state.lambda_ab,
        state.gamma_b,
        state.lambda_ba,
        h,
    )
    energy_ba = purification_bond_expectation(
        state.gamma_b,
        state.lambda_ba,
        state.gamma_a,
        state.lambda_ab,
        h,
    )
    return (ab = energy_ab, ba = energy_ba, mean = 0.5 * (energy_ab + energy_ba))
end

function finite_difference_uniform(
    x::Vector{Float64},
    y::Vector{Float64},
)::NamedTuple
    length(x) == length(y) || throw(DimensionMismatch("x and y must have equal length"))
    n = length(x)
    n >= 2 || throw(ArgumentError("at least two samples are required"))
    h = x[2] - x[1]
    h > 0 || throw(ArgumentError("x must be strictly increasing"))
    tolerance = 100 * eps(Float64) * max(1.0, maximum(abs, x), abs(h))
    all(isapprox(x[index] - x[index - 1], h; atol = tolerance, rtol = 0.0) for index in 3:n) ||
        throw(ArgumentError("x must be uniformly spaced"))

    first = zeros(Float64, n)
    second = zeros(Float64, n)

    if n == 2
        first .= (y[2] - y[1]) / h
        return (first = first, second = second)
    elseif n < 5
        first[1] = (-3 * y[1] + 4 * y[2] - y[3]) / (2 * h)
        first[end] = (3 * y[end] - 4 * y[end - 1] + y[end - 2]) / (2 * h)
        for index in 2:(n - 1)
            first[index] = (y[index + 1] - y[index - 1]) / (2 * h)
        end
        for index in 1:n
            window_start = clamp(index - 1, 1, n - 2)
            second[index] =
                (y[window_start] - 2 * y[window_start + 1] + y[window_start + 2]) / h^2
        end
        return (first = first, second = second)
    end

    first[1] =
        (-25 * y[1] + 48 * y[2] - 36 * y[3] + 16 * y[4] - 3 * y[5]) / (12 * h)
    first[2] =
        (-3 * y[1] - 10 * y[2] + 18 * y[3] - 6 * y[4] + y[5]) / (12 * h)
    for index in 3:(n - 2)
        first[index] =
            (y[index - 2] - 8 * y[index - 1] + 8 * y[index + 1] - y[index + 2]) /
            (12 * h)
    end
    first[end - 1] =
        (-y[end - 4] + 6 * y[end - 3] - 18 * y[end - 2] + 10 * y[end - 1] + 3 * y[end]) /
        (12 * h)
    first[end] =
        (3 * y[end - 4] - 16 * y[end - 3] + 36 * y[end - 2] - 48 * y[end - 1] + 25 * y[end]) /
        (12 * h)

    second[1] =
        (35 * y[1] - 104 * y[2] + 114 * y[3] - 56 * y[4] + 11 * y[5]) /
        (12 * h^2)
    second[2] =
        (11 * y[1] - 20 * y[2] + 6 * y[3] + 4 * y[4] - y[5]) / (12 * h^2)
    for index in 3:(n - 2)
        second[index] =
            (-y[index - 2] + 16 * y[index - 1] - 30 * y[index] + 16 * y[index + 1] - y[index + 2]) /
            (12 * h^2)
    end
    second[end - 1] =
        (-y[end - 4] + 4 * y[end - 3] + 6 * y[end - 2] - 20 * y[end - 1] + 11 * y[end]) /
        (12 * h^2)
    second[end] =
        (11 * y[end - 4] - 56 * y[end - 3] + 114 * y[end - 2] - 104 * y[end - 1] + 35 * y[end]) /
        (12 * h^2)
    return (first = first, second = second)
end

function atomic_write_json(path::String, payload)::Nothing
    mkpath(dirname(path))
    temporary, stream = mktemp(dirname(path); cleanup = false)
    try
        JSON.print(stream, payload, 2)
        write(stream, '\n')
        close(stream)
        mv(temporary, path; force = true)
    finally
        isopen(stream) && close(stream)
        isfile(temporary) && rm(temporary; force = true)
    end
    return nothing
end

function curve_payload(
    tau::Float64,
    Dc::Int,
    beta_max::Float64,
    pauli_convention::Bool,
    beta::Vector{Float64},
    log_partition::Vector{Float64},
    free_energy::Vector{Float64},
    exact_free_energy::Vector{Float64},
    exact_energy::Vector{Float64},
    exact_specific_heat::Vector{Float64},
    relative_error::Vector{Float64},
    max_truncerr::Vector{Float64},
    truncerr_ab::Vector{Float64},
    truncerr_ba::Vector{Float64},
    cumulative_truncerr::Vector{Float64},
    log_scale::Vector{Float64},
    log_norm_ab::Vector{Float64},
    log_norm_ba::Vector{Float64},
    kept_ab::Vector{Int},
    kept_ba::Vector{Int},
    direct_energy_beta::Vector{Float64},
    direct_energy_ab::Vector{Float64},
    direct_energy_ba::Vector{Float64},
    direct_energy::Vector{Float64},
)::Dict{String,Any}
    beta_free_energy = beta .* free_energy
    if length(beta) == 1
        energy = Any[nothing]
        specific_heat = Any[nothing]
    else
        derivatives = finite_difference_uniform(beta, beta_free_energy)
        energy = derivatives.first
        specific_heat = -beta .^ 2 .* derivatives.second
    end
    if length(direct_energy_beta) <= 1
        direct_specific_heat = Any[nothing for _ in direct_energy_beta]
    else
        direct_derivatives = finite_difference_uniform(direct_energy_beta, direct_energy)
        direct_specific_heat =
            -direct_energy_beta .^ 2 .* direct_derivatives.first
    end
    exact_specific_heat_at_direct_beta = [
        exact_thermo(value).specific_heat for value in direct_energy_beta
    ]
    direct_specific_heat_relative_error = [
        measured === nothing ? nothing : (measured - exact) / exact for
        (measured, exact) in zip(
            direct_specific_heat,
            exact_specific_heat_at_direct_beta,
        )
    ]

    return Dict{String,Any}(
        "tau" => tau,
        "Dc" => Dc,
        "beta_max" => beta_max,
        "pauli_convention" => pauli_convention,
        "beta" => beta,
        "temperature" => 1.0 ./ beta,
        "log_partition_per_site" => log_partition,
        "free_energy" => free_energy,
        "exact_free_energy" => exact_free_energy,
        "relative_free_energy_error" => relative_error,
        "energy" => energy,
        "exact_energy" => exact_energy,
        "specific_heat" => specific_heat,
        "exact_specific_heat" => exact_specific_heat,
        "max_truncerr" => max_truncerr,
        "truncerr_ab" => truncerr_ab,
        "truncerr_ba" => truncerr_ba,
        "cumulative_truncerr" => cumulative_truncerr,
        "log_scale" => log_scale,
        "log_norm_ab" => log_norm_ab,
        "log_norm_ba" => log_norm_ba,
        "kept_ab" => kept_ab,
        "kept_ba" => kept_ba,
        "direct_energy_beta" => direct_energy_beta,
        "direct_energy_ab" => direct_energy_ab,
        "direct_energy_ba" => direct_energy_ba,
        "direct_energy" => direct_energy,
        "direct_specific_heat" => direct_specific_heat,
        "exact_specific_heat_at_direct_beta" => exact_specific_heat_at_direct_beta,
        "direct_specific_heat_relative_error" => direct_specific_heat_relative_error,
    )
end

function run_curve(
    tau::Float64,
    Dc::Int,
    beta_max::Float64;
    cutoff::Float64 = 0.0,
    sample_every::Int = 1,
    progress_every::Int = 100,
    output::Union{Nothing,String} = nothing,
    pauli_convention::Bool = false,
)::Dict{String,Any}
    tau > 0 || throw(ArgumentError("tau must be positive"))
    Dc > 0 || throw(ArgumentError("Dc must be positive"))
    beta_max >= tau || throw(ArgumentError("beta_max must be at least tau"))
    sample_every > 0 || throw(ArgumentError("sample_every must be positive"))
    progress_every > 0 || throw(ArgumentError("progress_every must be positive"))
    steps = round(Int, beta_max / tau)
    isapprox(steps * tau, beta_max; atol = 100 * eps(Float64) * beta_max, rtol = 0.0) ||
        throw(ArgumentError("beta_max must be an integer multiple of tau"))

    state = identity_state()
    gate = vectorized_gate(tau; pauli_convention)
    beta = Float64[]
    log_partition = Float64[]
    free_energy = Float64[]
    exact_free_energy = Float64[]
    exact_energy = Float64[]
    exact_specific_heat = Float64[]
    relative_error = Float64[]
    max_truncerr = Float64[]
    truncerr_ab = Float64[]
    truncerr_ba = Float64[]
    cumulative_truncerr = Float64[]
    log_scale = Float64[]
    log_norm_ab = Float64[]
    log_norm_ba = Float64[]
    kept_ab = Int[]
    kept_ba = Int[]
    direct_energy_beta = Float64[]
    direct_energy_ab = Float64[]
    direct_energy_ba = Float64[]
    direct_energy = Float64[]
    largest_truncerr = 0.0
    total_truncerr = 0.0
    payload = Dict{String,Any}()

    for step in 1:steps
        diagnostic = step!(state, gate, tau, Dc; cutoff)
        largest_truncerr = max(
            largest_truncerr,
            diagnostic.truncerr_ab,
            diagnostic.truncerr_ba,
        )
        total_truncerr += diagnostic.truncerr_ab + diagnostic.truncerr_ba
        if step > steps - DIRECT_ENDPOINT_SAMPLES
            measured_energy = direct_bond_energies(
                state;
                pauli_convention,
            )
            push!(direct_energy_beta, state.beta)
            push!(direct_energy_ab, measured_energy.ab)
            push!(direct_energy_ba, measured_energy.ba)
            push!(direct_energy, measured_energy.mean)
        end
        save_sample = step % sample_every == 0 || step == steps
        current_relative_error = NaN

        if save_sample
            current_beta = state.beta
            current_log_partition = log_partition_per_site(state)
            current_free_energy = -current_log_partition / current_beta
            exact = exact_thermo(current_beta)
            current_relative_error =
                abs((current_free_energy - exact.free_energy) / exact.free_energy)

            push!(beta, current_beta)
            push!(log_partition, current_log_partition)
            push!(free_energy, current_free_energy)
            push!(exact_free_energy, exact.free_energy)
            push!(exact_energy, exact.energy)
            push!(exact_specific_heat, exact.specific_heat)
            push!(relative_error, current_relative_error)
            push!(max_truncerr, largest_truncerr)
            push!(truncerr_ab, diagnostic.truncerr_ab)
            push!(truncerr_ba, diagnostic.truncerr_ba)
            push!(cumulative_truncerr, total_truncerr)
            push!(log_scale, state.log_scale)
            push!(log_norm_ab, diagnostic.log_norm_ab)
            push!(log_norm_ba, diagnostic.log_norm_ba)
            push!(kept_ab, diagnostic.kept_ab)
            push!(kept_ba, diagnostic.kept_ba)

            payload = curve_payload(
                tau,
                Dc,
                beta_max,
                pauli_convention,
                beta,
                log_partition,
                free_energy,
                exact_free_energy,
                exact_energy,
                exact_specific_heat,
                relative_error,
                max_truncerr,
                truncerr_ab,
                truncerr_ba,
                cumulative_truncerr,
                log_scale,
                log_norm_ab,
                log_norm_ba,
                kept_ab,
                kept_ba,
                direct_energy_beta,
                direct_energy_ab,
                direct_energy_ba,
                direct_energy,
            )
            output === nothing || atomic_write_json(output, payload)
        end

        if step % progress_every == 0 || step == steps
            if !isfinite(current_relative_error)
                current_log_partition = log_partition_per_site(state)
                current_free_energy = -current_log_partition / state.beta
                exact = exact_thermo(state.beta)
                current_relative_error =
                    abs((current_free_energy - exact.free_energy) / exact.free_energy)
            end
            direct_status = ""
            if step == steps && !isempty(payload)
                direct_heat = payload["direct_specific_heat"][end]
                direct_relative_error = payload["direct_specific_heat_relative_error"][end]
                if direct_heat !== nothing
                    direct_status =
                        " direct_C=$(round(direct_heat; sigdigits=8))" *
                        " direct_C_rel=$(round(direct_relative_error; sigdigits=6))"
                end
            end
            println(
                "beta=$(round(state.beta; digits=8)) " *
                "log_scale=$(round(state.log_scale; sigdigits=8)) " *
                "max_truncerr=$(round(largest_truncerr; sigdigits=5)) " *
                "relative_free_energy_error=$(round(current_relative_error; sigdigits=5))" *
                direct_status,
            )
            flush(stdout)
        end
    end
    return payload
end

function bilayer_curve_payload(
    tau::Float64,
    Dc::Int,
    beta_max::Float64,
    beta::Vector{Float64},
    energy_ab::Vector{Float64},
    energy_ba::Vector{Float64},
    energy::Vector{Float64},
    exact_energy::Vector{Float64},
    exact_specific_heat::Vector{Float64},
    max_truncerr::Vector{Float64},
    truncerr_ab::Vector{Float64},
    truncerr_ba::Vector{Float64},
    cumulative_truncerr::Vector{Float64},
    kept_ab::Vector{Int},
    kept_ba::Vector{Int},
)::Dict{String,Any}
    if length(beta) <= 1
        specific_heat = Any[nothing for _ in beta]
    else
        derivatives = finite_difference_uniform(beta, energy)
        specific_heat = -beta .^ 2 .* derivatives.first
    end
    specific_heat_relative_error = [
        measured === nothing ? nothing : (measured - exact) / exact for
        (measured, exact) in zip(specific_heat, exact_specific_heat)
    ]
    return Dict{String,Any}(
        "method" => "bilayer LTRG++ purification",
        "tau" => tau,
        "Dc" => Dc,
        "beta_max" => beta_max,
        "beta" => beta,
        "temperature" => 1.0 ./ beta,
        "energy_ab" => energy_ab,
        "energy_ba" => energy_ba,
        "energy" => energy,
        "exact_energy" => exact_energy,
        "specific_heat" => specific_heat,
        "exact_specific_heat" => exact_specific_heat,
        "specific_heat_relative_error" => specific_heat_relative_error,
        "max_truncerr" => max_truncerr,
        "truncerr_ab" => truncerr_ab,
        "truncerr_ba" => truncerr_ba,
        "cumulative_truncerr" => cumulative_truncerr,
        "kept_ab" => kept_ab,
        "kept_ba" => kept_ba,
    )
end

function run_bilayer_curve(
    tau::Float64,
    Dc::Int,
    beta_max::Float64;
    J::Float64 = 1.0,
    cutoff::Float64 = 0.0,
    endpoint_samples::Int = DIRECT_ENDPOINT_SAMPLES,
    progress_every::Int = 100,
    output::Union{Nothing,String} = nothing,
    pauli_convention::Bool = false,
)::Dict{String,Any}
    tau > 0 || throw(ArgumentError("tau must be positive"))
    Dc > 0 || throw(ArgumentError("Dc must be positive"))
    beta_max >= tau || throw(ArgumentError("beta_max must be at least tau"))
    endpoint_samples >= 2 || throw(ArgumentError("endpoint_samples must be at least two"))
    progress_every > 0 || throw(ArgumentError("progress_every must be positive"))
    steps = round(Int, beta_max / tau)
    isapprox(steps * tau, beta_max; atol = 100 * eps(Float64) * beta_max, rtol = 0.0) ||
        throw(ArgumentError("beta_max must be an integer multiple of tau"))

    state = identity_state()
    quarter_gate = vectorized_gate(0.25 * tau, J; pauli_convention)
    half_gate = vectorized_gate(0.5 * tau, J; pauli_convention)
    beta = Float64[]
    energy_ab = Float64[]
    energy_ba = Float64[]
    energy = Float64[]
    exact_energy = Float64[]
    exact_specific_heat = Float64[]
    max_truncerr = Float64[]
    truncerr_ab = Float64[]
    truncerr_ba = Float64[]
    cumulative_truncerr = Float64[]
    kept_ab = Int[]
    kept_ba = Int[]
    largest_truncerr = 0.0
    total_truncerr = 0.0
    payload = Dict{String,Any}()

    for step in 1:steps
        diagnostic = bilayer_step!(
            state,
            quarter_gate,
            half_gate,
            tau,
            Dc;
            cutoff,
        )
        largest_truncerr = max(largest_truncerr, diagnostic.max_truncerr)
        total_truncerr += diagnostic.truncerr_total
        endpoint_step = step > steps - endpoint_samples

        if endpoint_step
            measured = purification_bond_energies(
                state,
                J;
                pauli_convention,
            )
            exact = exact_thermo(state.beta, J)
            push!(beta, state.beta)
            push!(energy_ab, measured.ab)
            push!(energy_ba, measured.ba)
            push!(energy, measured.mean)
            push!(exact_energy, exact.energy)
            push!(exact_specific_heat, exact.specific_heat)
            push!(max_truncerr, largest_truncerr)
            push!(truncerr_ab, diagnostic.truncerr_ab)
            push!(truncerr_ba, diagnostic.truncerr_ba)
            push!(cumulative_truncerr, total_truncerr)
            push!(kept_ab, diagnostic.kept_ab)
            push!(kept_ba, diagnostic.kept_ba)
            payload = bilayer_curve_payload(
                tau,
                Dc,
                beta_max,
                beta,
                energy_ab,
                energy_ba,
                energy,
                exact_energy,
                exact_specific_heat,
                max_truncerr,
                truncerr_ab,
                truncerr_ba,
                cumulative_truncerr,
                kept_ab,
                kept_ba,
            )
            output === nothing || atomic_write_json(output, payload)
        end

        if step % progress_every == 0 || step == steps
            if endpoint_step
                current_energy = energy[end]
            else
                current_energy = purification_bond_energies(
                    state,
                    J;
                    pauli_convention,
                ).mean
            end
            current_exact = exact_thermo(state.beta, J).energy
            energy_error = abs((current_energy - current_exact) / current_exact)
            heat_status = ""
            if step == steps
                heat = payload["specific_heat"][end]
                heat_error = payload["specific_heat_relative_error"][end]
                heat_status =
                    " C=$(round(heat; sigdigits=8))" *
                    " C_rel=$(round(heat_error; sigdigits=6))"
            end
            println(
                "beta=$(round(state.beta; digits=8)) " *
                "log_scale=$(round(state.log_scale; sigdigits=8)) " *
                "max_truncerr=$(round(largest_truncerr; sigdigits=5)) " *
                "relative_energy_error=$(round(energy_error; sigdigits=5))" *
                heat_status,
            )
            flush(stdout)
        end
    end
    return payload
end

function run_bilayer_cell!(
    run_spec::Dict{String,Any},
    cell::Dict{String,Any};
    progress_every::Int = 100,
)::Dict{String,Any}
    run_dir = String(run_spec["run_dir"])
    cell_id = String(cell["cell_id"])
    cell_dir = joinpath(run_dir, "cells", cell_id)
    data_path = joinpath(cell_dir, "data.json")
    manifest_path = joinpath(cell_dir, "manifest.json")
    params = cell["params"]
    curve = params["curve"]
    settings = merge(
        Dict{String,Any}(run_spec["settings"]),
        Dict{String,Any}(get(cell, "settings", Dict{String,Any}())),
    )
    provenance = merge(
        Dict{String,Any}(run_spec["provenance"]),
        Dict{String,Any}(get(cell, "provenance", Dict{String,Any}())),
    )
    started = time()
    manifest = Dict{String,Any}(
        "cell_id" => cell_id,
        "params" => params,
        "settings" => settings,
        "provenance" => provenance,
        "success" => false,
        "metrics" => Dict{String,Any}(
            "method" => "bilayer LTRG++ purification",
            "samples" => 0,
        ),
    )
    atomic_write_json(manifest_path, manifest)

    try
        pauli_convention = get(settings, "spin_convention", "S=sigma/2") != "S=sigma/2"
        data = run_bilayer_curve(
            Float64(curve["tau"]),
            Int(curve["Dc"]),
            Float64(curve["beta_max"]);
            J = Float64(get(settings, "J", 1.0)),
            cutoff = Float64(get(settings, "svd_cutoff", 0.0)),
            endpoint_samples = Int(get(
                settings,
                "direct_energy_endpoint_samples",
                DIRECT_ENDPOINT_SAMPLES,
            )),
            progress_every,
            output = data_path,
            pauli_convention,
        )
        manifest["success"] = true
        manifest["metrics"] = Dict{String,Any}(
            "method" => data["method"],
            "samples" => length(data["beta"]),
            "wall_seconds" => time() - started,
            "peak_rss_bytes" => Sys.maxrss(),
            "max_truncerr" => maximum(data["max_truncerr"]),
            "cumulative_truncerr" => data["cumulative_truncerr"][end],
            "energy_endpoint" => data["energy"][end],
            "specific_heat_endpoint" => data["specific_heat"][end],
            "exact_specific_heat_endpoint" => data["exact_specific_heat"][end],
            "specific_heat_relative_error" =>
                data["specific_heat_relative_error"][end],
        )
        atomic_write_json(manifest_path, manifest)
        return manifest
    catch error
        manifest["error"] = sprint(showerror, error)
        manifest["metrics"]["wall_seconds"] = time() - started
        atomic_write_json(manifest_path, manifest)
        rethrow()
    end
end

function run_cell!(
    run_spec::Dict{String,Any},
    cell::Dict{String,Any};
    progress_every::Int = 100,
    sample_every::Int = 1,
)::Dict{String,Any}
    run_dir = String(run_spec["run_dir"])
    cell_id = String(cell["cell_id"])
    cell_dir = joinpath(run_dir, "cells", cell_id)
    data_path = joinpath(cell_dir, "data.json")
    manifest_path = joinpath(cell_dir, "manifest.json")
    params = cell["params"]
    curve = params["curve"]
    settings = merge(
        Dict{String,Any}(run_spec["settings"]),
        Dict{String,Any}(get(cell, "settings", Dict{String,Any}())),
    )
    provenance = merge(
        Dict{String,Any}(run_spec["provenance"]),
        Dict{String,Any}(get(cell, "provenance", Dict{String,Any}())),
    )
    started = time()
    manifest = Dict{String,Any}(
        "cell_id" => cell_id,
        "params" => params,
        "settings" => settings,
        "provenance" => provenance,
        "success" => false,
        "metrics" => Dict{String,Any}("samples" => 0),
    )
    atomic_write_json(manifest_path, manifest)

    try
        pauli_convention = get(settings, "spin_convention", "S=sigma/2") != "S=sigma/2"
        data = run_curve(
            Float64(curve["tau"]),
            Int(curve["Dc"]),
            Float64(curve["beta_max"]);
            cutoff = Float64(get(settings, "svd_cutoff", 0.0)),
            sample_every,
            progress_every,
            output = data_path,
            pauli_convention,
        )
        manifest["success"] = true
        manifest["metrics"] = Dict{String,Any}(
            "samples" => length(data["beta"]),
            "wall_seconds" => time() - started,
            "peak_rss_bytes" => Sys.maxrss(),
            "max_truncerr" => maximum(data["max_truncerr"]),
            "cumulative_truncerr" => data["cumulative_truncerr"][end],
            "final_relative_free_energy_error" => data["relative_free_energy_error"][end],
            "direct_energy_endpoint" => data["direct_energy"][end],
            "direct_specific_heat_endpoint" => data["direct_specific_heat"][end],
            "exact_specific_heat_at_direct_beta" =>
                data["exact_specific_heat_at_direct_beta"][end],
            "direct_specific_heat_relative_error" =>
                data["direct_specific_heat_relative_error"][end],
        )
        atomic_write_json(manifest_path, manifest)
        return manifest
    catch error
        manifest["error"] = sprint(showerror, error)
        manifest["metrics"]["wall_seconds"] = time() - started
        atomic_write_json(manifest_path, manifest)
        rethrow()
    end
end

function run_negative_control(;
    tau::Float64 = 0.1,
    Dc::Int = 20,
    beta_max::Float64 = 2.0,
    progress_every::Int = 20,
    output::Union{Nothing,String} = nothing,
)::Dict{String,Any}
    curve = run_curve(
        tau,
        Dc,
        beta_max;
        progress_every,
        output,
        pauli_convention = true,
    )
    relative_error = curve["relative_free_energy_error"][end]
    return Dict{String,Any}(
        "caught" => relative_error > 0.05,
        "relative_free_energy_error" => relative_error,
        "spin_convention" => "Pauli bilinears",
        "expected_spin_convention" => "S=sigma/2",
        "tau" => tau,
        "Dc" => Dc,
        "beta_max" => beta_max,
    )
end

function parse_cli(args::Vector{String})::Dict{String,Any}
    options = Dict{String,Any}(
        "run_dir" => nothing,
        "quick" => false,
        "negative_control" => false,
    )
    index = 1
    while index <= length(args)
        argument = args[index]
        if argument == "--run-dir"
            index < length(args) || throw(ArgumentError("--run-dir requires a path"))
            index += 1
            options["run_dir"] = args[index]
        elseif argument == "--quick"
            options["quick"] = true
        elseif argument == "--negative-control"
            options["negative_control"] = true
        elseif argument in ("-h", "--help")
            options["help"] = true
        else
            throw(ArgumentError("unknown argument: $argument"))
        end
        index += 1
    end
    return options
end

function quick_run_spec(run_dir::String)::Dict{String,Any}
    curves = [
        Dict("id" => "tau0.1_dc100_b5", "tau" => 0.1, "Dc" => 100, "beta_max" => 0.5),
        Dict("id" => "tau0.05_dc50_b120", "tau" => 0.05, "Dc" => 50, "beta_max" => 0.5),
        Dict("id" => "tau0.05_dc100_b120", "tau" => 0.05, "Dc" => 100, "beta_max" => 0.5),
        Dict("id" => "tau0.05_dc150_b120", "tau" => 0.05, "Dc" => 150, "beta_max" => 0.5),
        Dict("id" => "tau0.02_dc100_b5", "tau" => 0.02, "Dc" => 100, "beta_max" => 0.2),
        Dict("id" => "tau0.02_dc150_b5", "tau" => 0.02, "Dc" => 150, "beta_max" => 0.2),
        Dict("id" => "tau0.01_dc150_b5", "tau" => 0.01, "Dc" => 150, "beta_max" => 0.1),
    ]
    cells = [
        Dict{String,Any}(
            "cell_id" => "cell-$(lpad(string(index), 4, '0'))",
            "params" => Dict("curve" => curve),
        ) for (index, curve) in enumerate(curves)
    ]
    return Dict{String,Any}(
        "run_id" => "xy-ltrg-quick",
        "run_dir" => run_dir,
        "settings" => Dict{String,Any}(
            "model" => "spin-1/2 XY chain",
            "spin_convention" => "S=sigma/2",
            "J" => 1.0,
            "svd_cutoff" => 0.0,
            "mode" => "quick integration check",
        ),
        "provenance" => Dict{String,Any}(
            "paper" => "arXiv:1011.0155",
            "purpose" => "quick integration check; not paper-result data",
        ),
        "cells" => cells,
    )
end

function successful_matching_cell(
    run_spec::Dict{String,Any},
    cell::Dict{String,Any},
)::Bool
    manifest_path = joinpath(
        String(run_spec["run_dir"]),
        "cells",
        String(cell["cell_id"]),
        "manifest.json",
    )
    isfile(manifest_path) || return false
    manifest = try
        JSON.parsefile(manifest_path)
    catch
        return false
    end
    return get(manifest, "success", false) === true &&
           get(manifest, "params", nothing) == cell["params"] &&
           get(manifest, "settings", nothing) == merge(
               Dict{String,Any}(run_spec["settings"]),
               Dict{String,Any}(get(cell, "settings", Dict{String,Any}())),
           ) &&
           get(manifest, "provenance", nothing) == merge(
               Dict{String,Any}(run_spec["provenance"]),
               Dict{String,Any}(get(cell, "provenance", Dict{String,Any}())),
           )
end

function python_executable(repo_root::String)::String
    candidate = joinpath(repo_root, ".venv", "bin", "python")
    isfile(candidate) && return candidate
    fallback = Sys.which("python3")
    fallback === nothing && error("Python interpreter not found")
    return fallback
end

function update_summary!(run_dir::String, additions::Dict{String,Any})::Nothing
    summary_path = joinpath(run_dir, "summary.json")
    summary = isfile(summary_path) ? JSON.parsefile(summary_path) : Dict{String,Any}()
    merge!(summary, additions)
    atomic_write_json(summary_path, summary)
    return nothing
end

function main(args::Vector{String} = ARGS)::Int
    options = parse_cli(args)
    if get(options, "help", false)
        println("usage: xy_ltrg_reproduction.jl --run-dir PATH [--quick | --negative-control]")
        return 0
    end
    options["run_dir"] === nothing && throw(ArgumentError("--run-dir is required"))
    run_dir = abspath(String(options["run_dir"]))
    mkpath(run_dir)
    LinearAlgebra.BLAS.set_num_threads(1)

    if options["negative_control"] && !options["quick"]
        output = joinpath(run_dir, "negative_control_curve.json")
        control = run_negative_control(output = output)
        update_summary!(run_dir, Dict{String,Any}("negative_control" => control))
        caught = control["caught"]
        relative_error = control["relative_free_energy_error"]
        println(
            "negative control caught=$caught " *
            "relative_free_energy_error=$relative_error",
        )
        flush(stdout)
        return control["caught"] ? 0 : 1
    end

    run_spec_path = joinpath(run_dir, "run_spec.json")
    run_spec = if options["quick"]
        spec = quick_run_spec(run_dir)
        atomic_write_json(run_spec_path, spec)
        spec
    else
        isfile(run_spec_path) || error("run specification not found: $run_spec_path")
        Dict{String,Any}(JSON.parsefile(run_spec_path))
    end
    run_spec["run_dir"] = run_dir

    total_started = time()
    for cell_any in run_spec["cells"]
        cell = Dict{String,Any}(cell_any)
        curve = cell["params"]["curve"]
        cell_id = cell["cell_id"]
        if successful_matching_cell(run_spec, cell)
            println("$cell_id: already complete; reusing declared curve")
            flush(stdout)
            continue
        end
        steps = round(Int, Float64(curve["beta_max"]) / Float64(curve["tau"]))
        progress_every = max(1, cld(steps, 25))
        tau = curve["tau"]
        Dc = curve["Dc"]
        beta_max = curve["beta_max"]
        println(
            "$cell_id: tau=$tau Dc=$Dc beta_max=$beta_max",
        )
        flush(stdout)
        run_cell!(run_spec, cell; progress_every)
    end

    repo_root = normpath(joinpath(@__DIR__, "..", "..", ".."))
    python = python_executable(repo_root)
    collector = joinpath(repo_root, "scripts", "parameter_scan.py")
    collector_command = Cmd([
        python,
        collector,
        "collect",
        "--run-spec",
        run_spec_path,
        "--success-field",
        "success",
        "--success-value",
        "true",
        "--value-field",
        "metrics.final_relative_free_energy_error",
        "--value-field",
        "metrics.wall_seconds",
    ])
    run(addenv(collector_command, "MPLCONFIGDIR" => "/tmp/matplotlib"))

    plotter = joinpath(@__DIR__, "plot_xy_ltrg.py")
    plot_arguments = [python, plotter, "--run-dir", run_dir]
    options["quick"] && push!(plot_arguments, "--quick")
    run(addenv(Cmd(plot_arguments), "MPLCONFIGDIR" => "/tmp/matplotlib"))

    additions = Dict{String,Any}(
        "julia_wall_seconds" => time() - total_started,
        "julia_peak_rss_bytes" => Sys.maxrss(),
        "mode" => options["quick"] ? "quick integration check" : "paper reproduction",
    )
    if options["quick"]
        control = run_negative_control(
            output = joinpath(run_dir, "negative_control_curve.json"),
        )
        additions["negative_control"] = control
    end
    update_summary!(run_dir, additions)
    return 0
end

end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(XYLTRGReproduction.main())
end
