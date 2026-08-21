struct WormParameters
    A_annihilate::Float64
    A_move::Float64
    A_kink::Float64
    tau_a::Float64
    tau_b::Float64
    tau_c::Float64

    function WormParameters(
        A_annihilate::Real,
        A_move::Real,
        A_kink::Real,
        tau_a::Real,
        tau_b::Real,
        tau_c::Real,
    )
        probabilities = (
            _finite_float("A_annihilate", A_annihilate),
            _finite_float("A_move", A_move),
            _finite_float("A_kink", A_kink),
        )
        all(0 < probability < 1 for probability in probabilities) ||
            throw(ArgumentError("worm family probabilities must lie in (0,1)"))
        isapprox(
            probabilities[1] + probabilities[2] + 2probabilities[3],
            1.0;
            atol=16eps(Float64),
            rtol=0,
        ) || throw(ArgumentError("A_annihilate + A_move + 2A_kink must equal one"))

        windows = (
            _finite_float("tau_a", tau_a),
            _finite_float("tau_b", tau_b),
            _finite_float("tau_c", tau_c),
        )
        all(window > 0 for window in windows) ||
            throw(ArgumentError("worm time windows must be positive"))
        return new(probabilities..., windows...)
    end
end

function _extended_normalization(beta::Real, nsites::Integer, omega_g::Real)
    inverse_temperature = _finite_float("beta", beta)
    inverse_temperature > 0 || throw(ArgumentError("beta must be positive"))
    nsites > 0 || throw(ArgumentError("nsites must be positive"))
    normalization = _finite_float("omega_g", omega_g)
    normalization > 0 || throw(ArgumentError("omega_g must be positive"))
    frozen = inverse_temperature * nsites
    normalization == frozen || throw(ArgumentError("omega_g must equal beta*nsites"))
    return frozen, normalization
end

function create_logratio(
    parameters::WormParameters;
    beta::Real,
    nsites::Integer,
    omega_g::Real,
    logF_ratio::Real,
)
    volume, normalization = _extended_normalization(beta, nsites, omega_g)
    weight = _finite_float("logF_ratio", logF_ratio)
    return log(parameters.A_annihilate) + log(parameters.tau_a) +
           log(volume / normalization) + weight
end

function annihilate_logratio(
    parameters::WormParameters;
    beta::Real,
    nsites::Integer,
    omega_g::Real,
    logF_ratio::Real,
)
    volume, normalization = _extended_normalization(beta, nsites, omega_g)
    weight = _finite_float("logF_ratio", logF_ratio)
    return -log(parameters.A_annihilate) - log(parameters.tau_a) +
           log(normalization / volume) + weight
end

move_logratio(; logF_ratio::Real) = _finite_float("logF_ratio", logF_ratio)

function insert_logratio(
    parameters::WormParameters;
    nk::Integer,
    logF_ratio::Real,
)
    nk >= 0 || throw(ArgumentError("nk must be nonnegative for insertion"))
    weight = _finite_float("logF_ratio", logF_ratio)
    return log(parameters.tau_c) - log(nk + 1) + weight
end

function delete_logratio(
    parameters::WormParameters;
    nk::Integer,
    logF_ratio::Real,
)
    nk > 0 || throw(ArgumentError("nk must be positive for deletion"))
    weight = _finite_float("logF_ratio", logF_ratio)
    return log(nk) - log(parameters.tau_c) + weight
end

function log_metropolis_acceptance(logratio::Real)
    checked = _finite_float("logratio", logratio)
    return min(0.0, checked)
end

@enum ProposalFamily::UInt8 begin
    CreateDefects = 1
    AnnihilateDefects = 2
    MoveDefect = 3
    InsertKink = 4
    DeleteKink = 5
end

struct ProposalRecord
    family::ProposalFamily
    direction::Int8
    directed_bond::Int
    log_forward_density::Float64
    log_reverse_density::Float64
    log_jacobian::Float64
    log_weight_ratio::Float64
    uniform::Float64
    log_acceptance_ratio::Float64
    accepted::Bool
end

function ProposalRecord(
    family::ProposalFamily;
    direction::Integer,
    directed_bond::Integer,
    log_forward_density::Real,
    log_reverse_density::Real,
    log_jacobian::Real,
    log_weight_ratio::Real,
    uniform::Real,
)
    direction in -1:1 || throw(ArgumentError("direction must be -1, 0, or 1"))
    directed_bond >= 0 || throw(ArgumentError("directed_bond must be nonnegative"))
    forward = _finite_float("log_forward_density", log_forward_density)
    reverse = _finite_float("log_reverse_density", log_reverse_density)
    jacobian = _finite_float("log_jacobian", log_jacobian)
    weight = _finite_float("log_weight_ratio", log_weight_ratio)
    draw = _finite_float("uniform", uniform)
    0 <= draw < 1 || throw(ArgumentError("uniform must satisfy 0 <= u < 1"))
    logratio = weight + reverse - forward + jacobian
    log_acceptance = log_metropolis_acceptance(logratio)
    accepted = draw == 0 || log(draw) < log_acceptance
    return ProposalRecord(
        family,
        Int8(direction),
        Int(directed_bond),
        forward,
        reverse,
        jacobian,
        weight,
        draw,
        logratio,
        accepted,
    )
end
