using TOML

struct SimulationConfig
    lattice::Symbol
    NumL1::Int
    NumL2::Int
    J1::Float64
    J2::Float64
    hTrfd::Float64
    BetaT::Float64
    IfSetDltau::Bool
    FixedDltau::Float64
    input_LTrot::Int
    LTrot::Int
    Dltau::Float64
    nLocal::Int
    nWolff::Int
    nWarm::Int
    NmBin::Int
    NSwep::Int
    NmMeaConfg::Int
    discard_initial_bins::Int
    trim_extrema::Bool
    statistics_mode::Symbol
    seed::UInt64
    initial_state::Symbol
    output_dir::String
    CpTau::Float64
    K_space::Float64
    K_tau::Float64
    p_space::Float64
    p_tau::Float64
    raw_input::Dict{String,Any}
end

function _required(raw::AbstractDict{String,<:Any}, key::String)
    haskey(raw, key) || throw(ArgumentError("missing required configuration key: $key"))
    return raw[key]
end

function _integer(raw::AbstractDict{String,<:Any}, key::String)
    value = _required(raw, key)
    value isa Integer && !(value isa Bool) ||
        throw(ArgumentError("$key must be an integer"))
    return Int(value)
end

function _number(raw::AbstractDict{String,<:Any}, key::String)
    value = _required(raw, key)
    value isa Real && !(value isa Bool) ||
        throw(ArgumentError("$key must be a real number"))
    result = Float64(value)
    isfinite(result) || throw(ArgumentError("$key must be finite"))
    return result
end

function _boolean(raw::AbstractDict{String,<:Any}, key::String)
    value = _required(raw, key)
    value isa Bool || throw(ArgumentError("$key must be true or false"))
    return value
end

function _string(raw::AbstractDict{String,<:Any}, key::String)
    value = _required(raw, key)
    value isa String || throw(ArgumentError("$key must be a string"))
    return value
end

function _require_at_least(value::Int, lower::Int, key::String)
    value >= lower || throw(ArgumentError("$key must be at least $lower"))
    return value
end

function _require_positive(value::Float64, key::String)
    value > 0 || throw(ArgumentError("$key must be positive"))
    return value
end

function _resolve_output_dir(raw_path::String, repo_root::AbstractString)
    root = abspath(normpath(repo_root))
    allowed_root = joinpath(root, "tracks", "qmc", "results", "Only-team")
    output_path = isabspath(raw_path) ?
                  abspath(normpath(raw_path)) :
                  abspath(normpath(joinpath(root, raw_path)))
    relative = relpath(output_path, allowed_root)
    outside =
        isabspath(relative) ||
        relative == "." ||
        relative == ".." ||
        startswith(relative, "../") ||
        startswith(relative, "..\\")
    outside && throw(
        ArgumentError(
            "output_dir must be below tracks/qmc/results/Only-team/",
        ),
    )
    return output_path
end

function derive_couplings(J1::Float64, hTrfd::Float64, Dltau::Float64)
    x = hTrfd * Dltau
    isfinite(x) && x > 0 ||
        throw(ArgumentError("hTrfd*Dltau must be finite and positive"))

    log_tanh_x = log(-expm1(-2x)) - log1p(exp(-2x))
    CpTau = 0.5 * log_tanh_x
    K_space = -Dltau * J1
    K_tau = -CpTau
    p_space = -expm1(-2K_space)
    p_tau = -expm1(-2K_tau)

    all(isfinite, (CpTau, K_space, K_tau, p_space, p_tau)) ||
        throw(ArgumentError("derived couplings must be finite"))
    CpTau < 0 || throw(ArgumentError("CpTau must be negative"))
    K_space > 0 || throw(ArgumentError("K_space must be positive"))
    K_tau > 0 || throw(ArgumentError("K_tau must be positive"))

    return (; CpTau, K_space, K_tau, p_space, p_tau)
end

function load_config(
    path::AbstractString;
    repo_root::AbstractString,
)::SimulationConfig
    raw = TOML.parsefile(path)

    lattice_name = _string(raw, "lattice")
    lattice_name in ("triangular", "honeycomb") ||
        throw(ArgumentError("lattice must be triangular or honeycomb"))
    lattice = Symbol(lattice_name)

    NumL1 = _require_at_least(_integer(raw, "NumL1"), 3, "NumL1")
    NumL2 = _require_at_least(_integer(raw, "NumL2"), 3, "NumL2")

    J1 = _number(raw, "J1")
    J1 < 0 || throw(ArgumentError("J1 must be negative"))
    J2 = _number(raw, "J2")
    J2 == 0 || throw(ArgumentError("J2 must equal zero"))
    hTrfd = _require_positive(_number(raw, "hTrfd"), "hTrfd")

    BetaT = _require_positive(_number(raw, "BetaT"), "BetaT")
    IfSetDltau = _boolean(raw, "IfSetDltau")
    FixedDltau =
        _require_positive(_number(raw, "FixedDltau"), "FixedDltau")
    input_LTrot = _require_at_least(_integer(raw, "LTrot"), 1, "LTrot")

    LTrot = IfSetDltau ? ceil(Int, BetaT / FixedDltau) : input_LTrot
    LTrot = isodd(LTrot) ? LTrot + 1 : LTrot
    Dltau = BetaT / LTrot

    nLocal = _require_at_least(_integer(raw, "nLocal"), 0, "nLocal")
    nWolff = _require_at_least(_integer(raw, "nWolff"), 0, "nWolff")
    nWarm = _require_at_least(_integer(raw, "nWarm"), 0, "nWarm")
    NmBin = _require_at_least(_integer(raw, "NmBin"), 0, "NmBin")
    NSwep = _require_at_least(_integer(raw, "NSwep"), 0, "NSwep")
    NmMeaConfg =
        _require_at_least(_integer(raw, "NmMeaConfg"), 1, "NmMeaConfg")
    NmMeaConfg <= LTrot ||
        throw(ArgumentError("NmMeaConfg must not exceed final LTrot"))

    discard_initial_bins = _integer(raw, "discard_initial_bins")
    0 <= discard_initial_bins < NmBin ||
        throw(
            ArgumentError(
                "discard_initial_bins must satisfy 0 <= value < NmBin",
            ),
        )
    trim_extrema = _boolean(raw, "trim_extrema")

    statistics_name = _string(raw, "statistics_mode")
    statistics_name == "bin_sem" ||
        throw(ArgumentError("statistics_mode must be bin_sem"))
    statistics_mode = Symbol(statistics_name)

    seed_input = _integer(raw, "seed")
    seed_input >= 0 || throw(ArgumentError("seed must be nonnegative"))
    seed = UInt64(seed_input)

    initial_name = _string(raw, "initial_state")
    initial_name in ("random", "ordered") ||
        throw(ArgumentError("initial_state must be random or ordered"))
    initial_state = Symbol(initial_name)

    output_dir = _resolve_output_dir(_string(raw, "output_dir"), repo_root)
    couplings = derive_couplings(J1, hTrfd, Dltau)

    return SimulationConfig(
        lattice,
        NumL1,
        NumL2,
        J1,
        J2,
        hTrfd,
        BetaT,
        IfSetDltau,
        FixedDltau,
        input_LTrot,
        LTrot,
        Dltau,
        nLocal,
        nWolff,
        nWarm,
        NmBin,
        NSwep,
        NmMeaConfg,
        discard_initial_bins,
        trim_extrema,
        statistics_mode,
        seed,
        initial_state,
        output_dir,
        couplings.CpTau,
        couplings.K_space,
        couplings.K_tau,
        couplings.p_space,
        couplings.p_tau,
        deepcopy(raw),
    )
end

function validate_statistics_feasibility(config::SimulationConfig)::Nothing
    config.NSwep > 0 ||
        throw(ArgumentError("NSwep must be positive for a production run"))

    remaining = config.NmBin - config.discard_initial_bins
    minimum = config.trim_extrema ? 4 : 2
    remaining >= minimum ||
        throw(
            ArgumentError(
                "bin filtering requires at least $minimum bins after initial-bin removal",
            ),
        )
    return nothing
end
