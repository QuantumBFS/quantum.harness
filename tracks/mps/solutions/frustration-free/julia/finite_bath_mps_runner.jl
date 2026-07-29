#!/usr/bin/env julia

using JSON3
using SHA
using LinearAlgebra
using ITensors
using ITensorMPS
using HDF5

include(joinpath(@__DIR__, "finite_bath_purification.jl"))
using .FiniteBathPurification: FiniteBathParameters
include(joinpath(@__DIR__, "finite_bath_observables.jl"))
using .FiniteBathObservables: ObservableInterrupted, finite_bath_observables
using .FiniteBathCheckpoint:
    CheckpointIdentity, load_current_checkpoint, write_checkpoint_generation

const RUNNER_SCHEMA_VERSION = 3
const RUNNER_VERSION = "3.1.0"
const CHECKPOINT_SCHEMA_VERSION = 1
const CHECKPOINT_WRITER_VERSION = "1.0.0"
const CONTINUATION_EXIT_CODE = 75
const PTHREAD_SIG_UNBLOCK = Cint(1)
const SHUTDOWN_REQUESTED = Threads.Atomic{Bool}(false)
const SIGUSR1_CONDITION = Ref{Union{Nothing,Base.AsyncCondition}}(nothing)
const SIGTERM_CONDITION = Ref{Union{Nothing,Base.AsyncCondition}}(nothing)
const SIGTERM_ASYNC_HANDLE = Ref{Ptr{Cvoid}}(C_NULL)

function sigterm_handler(::Cint)::Cvoid
    ccall(
        :uv_async_send,
        Cint,
        (Ptr{Cvoid},),
        SIGTERM_ASYNC_HANDLE[],
    )
    return
end

const SIGTERM_HANDLER = @cfunction(sigterm_handler, Cvoid, (Cint,))

function install_cooperative_shutdown_handlers()
    Threads.atomic_xchg!(SHUTDOWN_REQUESTED, false)
    usr1_condition = Base.AsyncCondition() do _
        Threads.atomic_xchg!(SHUTDOWN_REQUESTED, true)
    end
    Base.uv_unref(usr1_condition.handle)
    SIGUSR1_CONDITION[] = usr1_condition
    ccall(
        :jl_set_peek_cond,
        Cvoid,
        (Ptr{Cvoid},),
        usr1_condition.handle,
    )
    term_condition = Base.AsyncCondition() do _
        Threads.atomic_xchg!(SHUTDOWN_REQUESTED, true)
    end
    Base.uv_unref(term_condition.handle)
    SIGTERM_CONDITION[] = term_condition
    SIGTERM_ASYNC_HANDLE[] = term_condition.handle
    previous = ccall(
        :signal,
        Ptr{Cvoid},
        (Cint, Ptr{Cvoid}),
        Cint(Base.SIGTERM),
        SIGTERM_HANDLER,
    )
    previous == Ptr{Cvoid}(-1) &&
        error("could not install cooperative SIGTERM handler")
    signal_set = zeros(UInt8, 128)
    ccall(:sigemptyset, Cint, (Ptr{Cvoid},), signal_set) == 0 ||
        error("could not initialize cooperative SIGTERM set")
    ccall(
        :sigaddset,
        Cint,
        (Ptr{Cvoid}, Cint),
        signal_set,
        Cint(Base.SIGTERM),
    ) == 0 || error("could not add SIGTERM to cooperative signal set")
    ccall(
        :pthread_sigmask,
        Cint,
        (Cint, Ptr{Cvoid}, Ptr{Cvoid}),
        PTHREAD_SIG_UNBLOCK,
        signal_set,
        C_NULL,
    ) == 0 || error("could not unblock SIGTERM")
    return nothing
end

function cooperative_shutdown_requested()
    yield()
    return SHUTDOWN_REQUESTED[]
end

function strict_json_value(value, name)
    if value isa JSON3.Object
        converted = Dict{String,Any}()
        for (key, item) in pairs(value)
            string_key = String(key)
            haskey(converted, string_key) &&
                throw(ArgumentError("$name contains duplicate key $string_key"))
            converted[string_key] = strict_json_value(
                item, "$name.$string_key"
            )
        end
        return converted
    elseif value isa JSON3.Array
        return [
            strict_json_value(item, "$name[$index]")
            for (index, item) in enumerate(value)
        ]
    elseif value isa AbstractFloat
        isfinite(value) ||
            throw(ArgumentError("$name contains a non-finite float"))
        return Float64(value)
    elseif value === nothing || value isa Bool || value isa Integer ||
           value isa AbstractString
        return value
    end
    throw(ArgumentError("$name contains unsupported JSON value $(typeof(value))"))
end

function strict_json_read(raw, name)
    parsed = try
        JSON3.read(raw)
    catch error
        throw(ArgumentError("$name is invalid JSON: $(sprint(showerror, error))"))
    end
    return strict_json_value(parsed, name)
end

function canonical_request_json(value)
    if value === nothing
        return "null"
    elseif value isa AbstractFloat
        isfinite(value) ||
            throw(ArgumentError("request payload contains non-finite float"))
        isinteger(value) && return string(Int(value))
        return String(JSON3.write(value))
    elseif value isa Bool || value isa Integer || value isa AbstractString
        return String(JSON3.write(value))
    elseif value isa AbstractVector
        return "[" * join(canonical_request_json.(value), ",") * "]"
    elseif value isa AbstractDict
        keys_sorted = sort!(String.(collect(keys(value))))
        entries = [
            canonical_request_json(key) * ":" *
            canonical_request_json(value[key]) for key in keys_sorted
        ]
        return "{" * join(entries, ",") * "}"
    end
    throw(ArgumentError("request payload contains unsupported value"))
end

function canonical_artifact_json(value)
    if value isa AbstractFloat
        isfinite(value) ||
            throw(ArgumentError("artifact contains non-finite float"))
        return string(Float64(value))
    elseif value === nothing || value isa Bool || value isa Integer ||
           value isa AbstractString
        return String(JSON3.write(value))
    elseif value isa AbstractVector
        return "[" * join(canonical_artifact_json.(value), ",") * "]"
    elseif value isa AbstractDict
        keys_sorted = sort!(String.(collect(keys(value))))
        entries = [
            canonical_artifact_json(key) * ":" *
            canonical_artifact_json(value[key]) for key in keys_sorted
        ]
        return "{" * join(entries, ",") * "}"
    end
    throw(ArgumentError("artifact contains unsupported value"))
end

function require_exact_keys(value, expected, name)
    value isa AbstractDict || throw(ArgumentError("$name must be a JSON object"))
    actual = Set(String.(keys(value)))
    actual == Set(expected) ||
        throw(ArgumentError("$name keys do not match the supported schema"))
    return value
end

function finite_number(value, name)
    value isa Real && !(value isa Bool) ||
        throw(ArgumentError("$name must be a real number"))
    converted = Float64(value)
    isfinite(converted) || throw(ArgumentError("$name must be finite"))
    return converted
end

function positive_integer(value, name)
    value isa Integer && !(value isa Bool) && value > 0 ||
        throw(ArgumentError("$name must be a positive integer"))
    return Int(value)
end

function validate_digest(value, name)
    value isa AbstractString && occursin(r"^[0-9a-f]{64}$", value) ||
        throw(ArgumentError("$name must be 64 lowercase hexadecimal digits"))
    return String(value)
end

function validate_finite_tree(value, name = "result")
    if value === nothing || value isa Bool || value isa AbstractString ||
       value isa Integer
        return nothing
    elseif value isa AbstractFloat
        isfinite(value) || error("$name contains a non-finite float")
    elseif value isa AbstractVector
        foreach(item -> validate_finite_tree(item, name), value)
    elseif value isa NamedTuple
        foreach(item -> validate_finite_tree(item, name), values(value))
    elseif value isa AbstractDict
        foreach(item -> validate_finite_tree(item, name), values(value))
    else
        error("$name contains a non-JSON value of type $(typeof(value))")
    end
    return nothing
end

function authoritative_model_definition()
    path = joinpath(@__DIR__, "..", "model.json")
    filesize(path) <= 64 * 1024 ||
        throw(ArgumentError("model definition exceeds 64 KiB"))
    model = strict_json_read(read(path), "model definition")
    require_exact_keys(
        model,
        ["schema_version", "model_id", "parameters", "assertions", "conventions"],
        "model definition",
    )
    model["schema_version"] == 1 ||
        throw(ArgumentError("unsupported model definition schema"))
    model["model_id"] == "challenge-81-spinful-anderson-semicircular" ||
        throw(ArgumentError("unsupported model identity"))
    return model
end

function validate_bath_artifact(bath_artifact, bath_json, model_definition)
    require_exact_keys(bath_artifact, ["payload", "sha256"], "bath artifact")
    digest = validate_digest(bath_artifact["sha256"], "bath payload SHA256")
    bath = bath_artifact["payload"]
    require_exact_keys(
        bath,
        [
            "V", "broadening", "broadened_finite_bath_hybridization",
            "conventions", "epsilon", "frequency_grid", "parameters",
            "provenance", "schema_version", "target_continuum_hybridization",
        ],
        "bath payload",
    )
    canonical_file = strip(String(bath_json))
    prefix = "{\"payload\":"
    suffix = ",\"sha256\":\"$digest\"}"
    startswith(canonical_file, prefix) && endswith(canonical_file, suffix) ||
        throw(ArgumentError("bath artifact file is not canonical"))
    payload_start = ncodeunits(prefix) + 1
    payload_stop = ncodeunits(canonical_file) - ncodeunits(suffix)
    payload_bytes = codeunits(canonical_file)[payload_start:payload_stop]
    bytes2hex(sha256(payload_bytes)) == digest ||
        throw(ArgumentError("bath payload SHA256 mismatch"))
    bath["schema_version"] == 2 ||
        throw(ArgumentError("unsupported bath schema version"))
    parameters = require_exact_keys(
        bath["parameters"], ["bandwidth", "gamma", "n_bath"], "bath parameters"
    )
    bandwidth = finite_number(parameters["bandwidth"], "bandwidth")
    gamma = finite_number(parameters["gamma"], "gamma")
    n_bath = positive_integer(parameters["n_bath"], "n_bath")
    bandwidth > 0 || throw(ArgumentError("bandwidth must be positive"))
    gamma >= 0 || throw(ArgumentError("gamma must be nonnegative"))
    expected_model = model_definition["parameters"]
    bandwidth == finite_number(expected_model["D"], "model D") ||
        throw(ArgumentError("bath bandwidth does not match model D"))
    gamma == finite_number(expected_model["Gamma"], "model Gamma") ||
        throw(ArgumentError("bath gamma does not match model Gamma"))

    conventions = require_exact_keys(
        bath["conventions"],
        ["hybridization", "quadrature", "target_continuum", "ordering", "epsilon", "V_squared"],
        "bath conventions",
    )
    for name in keys(conventions)
        conventions[name] == model_definition["conventions"][name] ||
            throw(ArgumentError("unsupported bath $name convention"))
    end
    provenance = require_exact_keys(
        bath["provenance"],
        ["module", "module_version", "python_version", "numpy_version", "schema_version"],
        "bath provenance",
    )
    provenance["module"] == "bath" && provenance["schema_version"] == 2 ||
        throw(ArgumentError("unsupported bath provenance"))

    epsilon = [finite_number(value, "epsilon") for value in bath["epsilon"]]
    coupling = [finite_number(value, "V") for value in bath["V"]]
    length(epsilon) == n_bath == length(coupling) ||
        throw(ArgumentError("bath arrays must have n_bath entries"))
    all(>=(0.0), coupling) || throw(ArgumentError("V must be nonnegative"))
    expected_epsilon = [
        bandwidth * cos(k * pi / (n_bath + 1)) for k in 1:n_bath
    ]
    expected_coupling = [
        sqrt(
            gamma * bandwidth / (n_bath + 1) *
            sin(k * pi / (n_bath + 1))^2
        ) for k in 1:n_bath
    ]
    all(isapprox.(epsilon, expected_epsilon; rtol = 1e-13, atol = 1e-15)) ||
        throw(ArgumentError("epsilon does not match quadrature"))
    all(isapprox.(coupling, expected_coupling; rtol = 1e-13, atol = 1e-15)) ||
        throw(ArgumentError("V does not match quadrature"))
    isapprox(
        pi * sum(abs2, coupling),
        pi * gamma * bandwidth / 2;
        rtol = 1e-13,
        atol = 1e-15,
    ) || throw(ArgumentError("gamma normalization failed"))

    grid = [finite_number(value, "frequency grid") for value in bath["frequency_grid"]]
    length(grid) >= 2 && all(diff(grid) .> 0) ||
        throw(ArgumentError("frequency grid must be strictly increasing"))
    target = [
        finite_number(value, "target hybridization")
        for value in bath["target_continuum_hybridization"]
    ]
    broadened = [
        finite_number(value, "broadened hybridization")
        for value in bath["broadened_finite_bath_hybridization"]
    ]
    length(target) == length(grid) == length(broadened) ||
        throw(ArgumentError("hybridization arrays must match frequency grid"))
    expected_target = [
        abs(omega) <= bandwidth ?
        gamma * sqrt(max(0.0, 1 - (omega / bandwidth)^2)) : 0.0
        for omega in grid
    ]
    all(isapprox.(target, expected_target; rtol = 1e-13, atol = 1e-15)) ||
        throw(ArgumentError("target hybridization does not match model"))
    broadening = require_exact_keys(
        bath["broadening"],
        ["kernel", "width", "width_rule", "interpretation"],
        "bath broadening",
    )
    width = finite_number(broadening["width"], "broadening width")
    broadening["kernel"] == "normalized_gaussian" &&
        broadening["width_rule"] == "bandwidth / (n_bath + 1)" &&
        broadening["interpretation"] ==
            "broadened finite-bath realization; not the fitted continuum" &&
        width == bandwidth / (n_bath + 1) ||
        throw(ArgumentError("unsupported bath broadening"))
    expected_broadened = [
        pi * sum(
            coupling[index]^2 *
            exp(-0.5 * ((omega - epsilon[index]) / width)^2) /
            (sqrt(2pi) * width) for index in eachindex(epsilon)
        ) for omega in grid
    ]
    all(isapprox.(broadened, expected_broadened; rtol = 1e-13, atol = 1e-15)) ||
        throw(ArgumentError("broadened hybridization does not match bath"))
    return (; bath, epsilon, coupling)
end

const CHAIN_MAPPING_PAYLOAD_KEYS = [
    "Q",
    "chain_hopping",
    "chain_onsite",
    "conventions",
    "deflation_boundaries",
    "lambda",
    "n_bath",
    "numerics",
    "provenance",
    "representation",
    "schema_version",
    "source_bath_schema_version",
    "source_bath_sha256",
]
const CHAIN_MAPPING_CONVENTIONS = Dict(
    "star_matrix" => "E = diag(epsilon)",
    "coupling_gauge" => "v is real and componentwise nonnegative",
    "initial_vector" => "q0 = v / norm(v) when norm(v) > 0",
    "spin_transform" => "the same real Q is used for up and down",
    "chemical_potential" => "transform E before subtracting mu",
    "hopping_gauge" => "chain hoppings are nonnegative",
    "breakdown" => "deterministic canonical coordinate deflation",
    "decoupled" => "v = 0 maps with Q = I",
)
const CHAIN_MAPPING_NUMERICS_KEYS = [
    "algorithm",
    "breakdown_tolerance",
    "breakdown_tolerance_rule",
    "coupling_max_error",
    "off_tridiagonal_max_abs",
    "orthogonality_max_error",
]
const CHAIN_MAPPING_PROVENANCE_KEYS = [
    "module",
    "module_version",
    "numpy_version",
    "python_version",
    "schema_version",
]
const CHAIN_MAPPING_PROVENANCE = Dict(
    "module" => "chain_mapping",
    "module_version" => "1.0.0",
    "numpy_version" => "2.5.1",
    "python_version" => "3.12.13",
    "schema_version" => 1,
)
const CHAIN_MAPPING_TOLERANCE_RULE =
    "64 * eps(float64) * max(1, norm(E, inf)) * n_bath"

function finite_vector(value, name)
    value isa AbstractVector ||
        throw(ArgumentError("$name must be an array"))
    return [finite_number(entry, "$name values") for entry in value]
end

function maximum_absolute(value)
    return maximum(abs, value; init = 0.0)
end

function canonical_chain_mapping_json(mapping_artifact)
    canonical = deepcopy(mapping_artifact)
    mapping = canonical["payload"]
    mapping["lambda"] = finite_number(mapping["lambda"], "chain mapping lambda")
    mapping["chain_onsite"] =
        finite_vector(mapping["chain_onsite"], "chain onsite")
    mapping["chain_hopping"] =
        finite_vector(mapping["chain_hopping"], "chain hopping")
    Q_rows = mapping["Q"]
    Q_rows isa AbstractVector ||
        throw(ArgumentError("chain mapping Q must be an array"))
    mapping["Q"] = [
        finite_vector(row, "chain mapping Q row") for row in Q_rows
    ]
    numerics = mapping["numerics"]
    numerics isa AbstractDict ||
        throw(ArgumentError("chain mapping numerics must be a JSON object"))
    for key in (
        "breakdown_tolerance",
        "coupling_max_error",
        "off_tridiagonal_max_abs",
        "orthogonality_max_error",
    )
        numerics[key] = finite_number(numerics[key], "chain mapping $key")
    end
    return canonical_artifact_json(canonical) * "\n"
end

function fixed_order_chain_mapping_diagnostics(epsilon, coupling, Q, lambda)
    # This is the one-based Julia transcription of chain_mapping.py's
    # zero-based fixed-order scalar convention. Keep every loop ascending and
    # every product/addition split exactly as written: no BLAS, reductions,
    # muladd, @fastmath, or reassociation is allowed in this replay.
    n_bath = length(epsilon)
    orthogonality_error = 0.0
    for left in 1:n_bath, right in 1:n_bath
        overlap = 0.0
        for row in 1:n_bath
            product = Q[row, left] * Q[row, right]
            overlap = overlap + product
        end
        left == right && (overlap = overlap - 1.0)
        orthogonality_error = max(orthogonality_error, abs(overlap))
    end

    off_tridiagonal_error = 0.0
    for left in 1:n_bath, right in 1:n_bath
        abs(left - right) <= 1 && continue
        forward = 0.0
        reverse = 0.0
        for row in 1:n_bath
            weighted_left = Q[row, left] * epsilon[row]
            forward = forward + weighted_left * Q[row, right]
            weighted_right = Q[row, right] * epsilon[row]
            reverse = reverse + weighted_right * Q[row, left]
        end
        symmetrized = (forward + reverse) / 2.0
        off_tridiagonal_error =
            max(off_tridiagonal_error, abs(symmetrized))
    end

    coupling_error = 0.0
    for column in 1:n_bath
        transformed_coupling = 0.0
        for row in 1:n_bath
            product = Q[row, column] * coupling[row]
            transformed_coupling = transformed_coupling + product
        end
        target = column == 1 ? lambda : 0.0
        coupling_error =
            max(coupling_error, abs(transformed_coupling - target))
    end
    return Dict(
        "orthogonality_max_error" => orthogonality_error,
        "off_tridiagonal_max_abs" => off_tridiagonal_error,
        "coupling_max_error" => coupling_error,
    )
end

function validate_chain_mapping_artifact(
    mapping_artifact, mapping_json, bath_artifact
)
    mapping_json isa AbstractString ||
        throw(ArgumentError("chain mapping artifact JSON must be a string"))
    require_exact_keys(
        mapping_artifact, ["payload", "sha256"], "chain mapping artifact"
    )
    mapping_digest =
        validate_digest(mapping_artifact["sha256"], "chain mapping payload SHA256")
    prefix = "{\"payload\":"
    suffix = ",\"sha256\":\"$mapping_digest\"}\n"
    startswith(mapping_json, prefix) && endswith(mapping_json, suffix) ||
        throw(ArgumentError("chain mapping artifact file is not canonical"))
    payload_start = ncodeunits(prefix) + 1
    payload_stop = ncodeunits(mapping_json) - ncodeunits(suffix)
    payload_bytes = codeunits(mapping_json)[payload_start:payload_stop]
    mapping = require_exact_keys(
        mapping_artifact["payload"],
        CHAIN_MAPPING_PAYLOAD_KEYS,
        "chain mapping payload",
    )
    conventions = require_exact_keys(
        mapping["conventions"],
        collect(keys(CHAIN_MAPPING_CONVENTIONS)),
        "chain mapping conventions",
    )
    numerics = require_exact_keys(
        mapping["numerics"],
        CHAIN_MAPPING_NUMERICS_KEYS,
        "chain mapping numerics",
    )
    provenance = require_exact_keys(
        mapping["provenance"],
        CHAIN_MAPPING_PROVENANCE_KEYS,
        "chain mapping provenance",
    )
    canonical_chain_mapping_json(mapping_artifact) == mapping_json ||
        throw(ArgumentError("chain mapping artifact file is not canonical"))
    bytes2hex(sha256(payload_bytes)) == mapping_digest ||
        throw(ArgumentError("chain mapping payload SHA256 mismatch"))

    mapping["schema_version"] == 1 ||
        throw(ArgumentError("unsupported chain mapping schema version"))
    mapping["representation"] == "finite_chain" ||
        throw(ArgumentError("unsupported chain mapping representation"))
    mapping["source_bath_schema_version"] ==
        bath_artifact["payload"]["schema_version"] ||
        throw(ArgumentError("chain mapping source bath schema mismatch"))
    source_digest = validate_digest(
        mapping["source_bath_sha256"], "chain mapping source bath SHA256"
    )
    source_digest == bath_artifact["sha256"] ||
        throw(ArgumentError("chain mapping source bath SHA256 mismatch"))

    conventions == CHAIN_MAPPING_CONVENTIONS ||
        throw(ArgumentError("unsupported chain mapping conventions"))
    numerics["algorithm"] == "two-pass fully reorthogonalized Lanczos" ||
        throw(ArgumentError("chain mapping algorithm mismatch"))
    numerics["breakdown_tolerance_rule"] == CHAIN_MAPPING_TOLERANCE_RULE ||
        throw(ArgumentError("chain mapping breakdown_tolerance_rule mismatch"))
    for (key, expected) in CHAIN_MAPPING_PROVENANCE
        provenance[key] == expected ||
            throw(ArgumentError("chain mapping provenance $key mismatch"))
    end

    epsilon = finite_vector(bath_artifact["payload"]["epsilon"], "bath epsilon")
    coupling = finite_vector(bath_artifact["payload"]["V"], "bath V")
    n_bath = positive_integer(mapping["n_bath"], "chain mapping n_bath")
    n_bath == length(epsilon) == length(coupling) ||
        throw(ArgumentError("chain mapping size does not match source bath"))
    lambda = finite_number(mapping["lambda"], "chain mapping lambda")
    lambda >= 0 ||
        throw(ArgumentError("chain mapping lambda must be nonnegative"))
    onsite = finite_vector(mapping["chain_onsite"], "chain onsite")
    hopping = finite_vector(mapping["chain_hopping"], "chain hopping")
    length(onsite) == n_bath ||
        throw(ArgumentError("chain onsite length must equal n_bath"))
    length(hopping) == max(0, n_bath - 1) ||
        throw(ArgumentError("chain hopping length must equal n_bath minus one"))
    all(>=(0.0), hopping) ||
        throw(ArgumentError("chain hopping must be nonnegative"))

    Q_rows = mapping["Q"]
    Q_rows isa AbstractVector && length(Q_rows) == n_bath ||
        throw(ArgumentError("chain mapping Q must have n_bath rows"))
    all(row -> row isa AbstractVector && length(row) == n_bath, Q_rows) ||
        throw(ArgumentError("chain mapping Q must be square"))
    Q = Matrix{Float64}(undef, n_bath, n_bath)
    for row in 1:n_bath, column in 1:n_bath
        Q[row, column] =
            finite_number(Q_rows[row][column], "chain mapping Q")
    end

    boundaries = mapping["deflation_boundaries"]
    boundaries isa AbstractVector ||
        throw(ArgumentError("deflation boundaries must be an array"))
    all(
        boundary ->
            boundary isa Integer &&
            !(boundary isa Bool) &&
            0 <= boundary < n_bath - 1,
        boundaries,
    ) || throw(ArgumentError("deflation boundaries are invalid"))
    issorted(boundaries) && allunique(boundaries) ||
        throw(ArgumentError("deflation boundaries must be sorted and unique"))

    replayed_diagnostics =
        fixed_order_chain_mapping_diagnostics(epsilon, coupling, Q, lambda)
    for key in (
        "orthogonality_max_error",
        "off_tridiagonal_max_abs",
        "coupling_max_error",
    )
        reported = finite_number(numerics[key], "chain mapping $key")
        replayed = finite_number(
            replayed_diagnostics[key], "replayed chain mapping $key"
        )
        reported == replayed ||
            throw(ArgumentError("chain mapping $key mismatch"))
    end
    expected_tolerance =
        64 * eps(Float64) * max(1.0, norm(epsilon, Inf)) * n_bath
    finite_number(
        numerics["breakdown_tolerance"], "chain mapping breakdown tolerance"
    ) == expected_tolerance ||
        throw(ArgumentError("chain mapping breakdown_tolerance mismatch"))
    validation_tolerance = 4 * expected_tolerance

    identity_error = maximum_absolute(Q' * Q - I)
    identity_error <= validation_tolerance ||
        throw(ArgumentError("chain mapping Q is not orthogonal"))
    transformed = Q' * Diagonal(epsilon) * Q
    transformed = (transformed + transformed') / 2
    off_tridiagonal_error = maximum(
        (
            abs(transformed[row, column]) for row in 1:n_bath,
            column in 1:n_bath if abs(row - column) > 1
        );
        init = 0.0,
    )
    off_tridiagonal_error <= validation_tolerance ||
        throw(ArgumentError("chain mapping transform is not tridiagonal"))
    maximum_absolute(diag(transformed) - onsite) <= validation_tolerance ||
        throw(ArgumentError("chain onsite does not match Q' * E * Q"))
    boundary_set = Set(Int.(boundaries))
    for index in 1:(n_bath - 1)
        expected_hopping =
            (index - 1) in boundary_set ? 0.0 : transformed[index, index + 1]
        expected_hopping >= -validation_tolerance ||
            throw(ArgumentError("chain transform has negative hopping"))
        abs(hopping[index] - max(0.0, expected_hopping)) <=
            validation_tolerance ||
            throw(ArgumentError("chain hopping does not match Q' * E * Q"))
    end
    target = zeros(n_bath)
    target[1] = lambda
    maximum_absolute(Q' * coupling - target) <= validation_tolerance ||
        throw(ArgumentError("chain mapping coupling invariant failed"))
    abs(lambda - norm(coupling)) <= validation_tolerance ||
        throw(ArgumentError("chain mapping lambda does not match bath V"))
    if iszero(norm(coupling))
        Q == Matrix{Float64}(I, n_bath, n_bath) ||
            throw(ArgumentError("decoupled chain mapping Q must be identity"))
        onsite == epsilon ||
            throw(ArgumentError("decoupled chain onsite must equal epsilon"))
        all(iszero, hopping) ||
            throw(ArgumentError("decoupled chain hopping must be zero"))
    end

    return (;
        mapping,
        mapping_sha256 = mapping_digest,
        chain_onsite = onsite,
        chain_hopping = hopping,
        lambda,
    )
end

function read_request(path)
    raw = read(path)
    request = strict_json_read(raw, "request")
    require_exact_keys(request, ["payload_json", "sha256"], "request")
    reported_payload_digest =
        validate_digest(request["sha256"], "request payload SHA256")
    payload_json = request["payload_json"]
    payload_json isa AbstractString ||
        throw(ArgumentError("request payload_json must be a string"))
    payload_digest = bytes2hex(sha256(codeunits(payload_json)))
    payload_digest == reported_payload_digest ||
        throw(
            ArgumentError(
                "request payload SHA256 mismatch: reported=" *
                "$reported_payload_digest recomputed=$payload_digest"
            ),
        )
    payload = strict_json_read(payload_json, "request payload")
    payload = require_exact_keys(
        payload,
        [
            "schema_version",
            "bath_artifact_json",
            "bath_artifact_file_sha256",
            "bath_geometry",
            "checkpoint",
            "model",
            "tau",
            "solver_settings",
        ],
        "request payload",
    )
    canonical_request_json(payload) == payload_json ||
        throw(ArgumentError("request payload_json is not canonical"))
    payload["schema_version"] == RUNNER_SCHEMA_VERSION ||
        throw(ArgumentError("unsupported request schema version"))

    bath_json = payload["bath_artifact_json"]
    bath_json isa AbstractString ||
        throw(ArgumentError("bath_artifact_json must be a string"))
    bath_file_digest =
        validate_digest(payload["bath_artifact_file_sha256"], "bath artifact file SHA256")
    bytes2hex(sha256(codeunits(bath_json))) == bath_file_digest ||
        throw(ArgumentError("bath artifact file SHA256 mismatch"))
    bath_artifact = strict_json_read(bath_json, "bath artifact")
    model_definition = authoritative_model_definition()
    validated_bath =
        validate_bath_artifact(bath_artifact, bath_json, model_definition)
    epsilon = validated_bath.epsilon
    coupling = validated_bath.coupling

    geometry = require_exact_keys(
        payload["bath_geometry"],
        [
            "representation",
            "chain_mapping_artifact_json",
            "chain_mapping_artifact_file_sha256",
        ],
        "bath geometry",
    )
    representation = geometry["representation"]
    representation isa AbstractString ||
        throw(ArgumentError("bath representation must be a string"))
    mapping_sha256 = nothing
    validated_mapping = nothing
    if representation == "direct_star"
        geometry["chain_mapping_artifact_json"] === nothing &&
            geometry["chain_mapping_artifact_file_sha256"] === nothing ||
            throw(ArgumentError("direct-star geometry cannot consume a chain mapping"))
    elseif representation == "chain"
        mapping_json = geometry["chain_mapping_artifact_json"]
        mapping_json isa AbstractString ||
            throw(ArgumentError("chain geometry requires a mapping artifact"))
        mapping_file_digest = validate_digest(
            geometry["chain_mapping_artifact_file_sha256"],
            "chain mapping artifact file SHA256",
        )
        bytes2hex(sha256(codeunits(mapping_json))) == mapping_file_digest ||
            throw(ArgumentError("chain mapping artifact file SHA256 mismatch"))
        mapping_artifact =
            strict_json_read(mapping_json, "chain mapping artifact")
        validated_mapping = validate_chain_mapping_artifact(
            mapping_artifact, mapping_json, bath_artifact
        )
        mapping_sha256 = validated_mapping.mapping_sha256
    else
        throw(
            ArgumentError(
                "bath representation must be direct_star or chain"
            ),
        )
    end

    checkpoint = require_exact_keys(
        payload["checkpoint"],
        [
            "checkpoint_schema",
            "writer_version",
            "source_hashes",
            "project_toml_sha256",
            "manifest_toml_sha256",
        ],
        "checkpoint",
    )
    checkpoint["checkpoint_schema"] == CHECKPOINT_SCHEMA_VERSION ||
        throw(ArgumentError("unsupported checkpoint schema version"))
    checkpoint["writer_version"] == CHECKPOINT_WRITER_VERSION ||
        throw(ArgumentError("unsupported checkpoint writer version"))
    source_hashes = require_exact_keys(
        checkpoint["source_hashes"],
        [
            "chain_mapping",
            "checkpoint",
            "model_definition",
            "observables",
            "purification",
            "runner",
        ],
        "checkpoint source hashes",
    )
    source_paths = Dict(
        "chain_mapping" => joinpath(@__DIR__, "..", "chain_mapping.py"),
        "checkpoint" => joinpath(@__DIR__, "finite_bath_checkpoint.jl"),
        "model_definition" => joinpath(@__DIR__, "..", "model.json"),
        "observables" => joinpath(@__DIR__, "finite_bath_observables.jl"),
        "purification" => joinpath(@__DIR__, "finite_bath_purification.jl"),
        "runner" => @__FILE__,
    )
    for (name, path) in source_paths
        validate_digest(source_hashes[name], "checkpoint source hash $name") ==
            source_sha256(path) ||
            throw(ArgumentError("checkpoint source hash mismatch: $name"))
    end
    project_hash =
        validate_digest(checkpoint["project_toml_sha256"], "checkpoint project SHA256")
    manifest_hash =
        validate_digest(checkpoint["manifest_toml_sha256"], "checkpoint manifest SHA256")
    project_hash == source_sha256(joinpath(@__DIR__, "Project.toml")) ||
        throw(ArgumentError("checkpoint project SHA256 mismatch"))
    manifest_hash == source_sha256(joinpath(@__DIR__, "Manifest.toml")) ||
        throw(ArgumentError("checkpoint manifest SHA256 mismatch"))

    model = require_exact_keys(
        payload["model"], ["U", "beta", "epsilon_d", "mu"], "model"
    )
    U = finite_number(model["U"], "U")
    beta = finite_number(model["beta"], "beta")
    epsilon_d = finite_number(model["epsilon_d"], "epsilon_d")
    mu = finite_number(model["mu"], "mu")
    U >= 0 || throw(ArgumentError("U must be nonnegative"))
    beta > 0 || throw(ArgumentError("beta must be positive"))
    expected_model = model_definition["parameters"]
    U == expected_model["U"] &&
        epsilon_d == expected_model["epsilon_d"] &&
        mu == expected_model["mu"] ||
        throw(ArgumentError("request model does not match authoritative model"))

    tau = [finite_number(value, "tau") for value in payload["tau"]]
    isempty(tau) && throw(ArgumentError("tau must not be empty"))
    all(point -> 0 <= point <= beta, tau) ||
        throw(ArgumentError("tau must lie in [0, beta]"))

    settings = require_exact_keys(
        payload["solver_settings"],
        ["cutoff", "krylov_expansion_dim", "maxdim", "time_step"],
        "solver settings",
    )
    time_step = finite_number(settings["time_step"], "time_step")
    cutoff = finite_number(settings["cutoff"], "cutoff")
    maxdim = positive_integer(settings["maxdim"], "maxdim")
    krylov_expansion_dim = settings["krylov_expansion_dim"]
    krylov_expansion_dim isa Integer &&
        !(krylov_expansion_dim isa Bool) &&
        krylov_expansion_dim >= 0 ||
        throw(
            ArgumentError(
                "krylov_expansion_dim must be a nonnegative integer"
            ),
        )
    krylov_expansion_dim = Int(krylov_expansion_dim)
    time_step > 0 || throw(ArgumentError("time_step must be positive"))
    cutoff >= 0 || throw(ArgumentError("cutoff must be nonnegative"))

    parameters =
        representation == "direct_star" ?
        FiniteBathParameters(epsilon, coupling; U, epsilon_d, mu) :
        FiniteBathParameters(
            :chain;
            epsilon,
            V = [validated_mapping.lambda; zeros(length(epsilon) - 1)],
            chain_onsite = validated_mapping.chain_onsite,
            chain_hopping = validated_mapping.chain_hopping,
            lambda = validated_mapping.lambda,
            mapping_sha256,
            U,
            epsilon_d,
            mu,
        )
    return (;
        raw,
        request,
        payload,
        payload_digest,
        bath_sha256 = String(bath_artifact["sha256"]),
        bath_representation = String(representation),
        mapping_sha256,
        parameters,
        beta,
        tau,
        checkpoint,
        settings = (; time_step, cutoff, maxdim, krylov_expansion_dim),
    )
end

function branch_diagnostics(entries)
    return [
        (;
            tau = entry.tau,
            spin = String(entry.spin),
            insertion = String(entry.insertion),
            branch_status = String(entry.branch_status),
            max_link_dimension = entry.max_link_dimension,
            maximum_link_dimensions_by_bond =
                entry.maximum_link_dimensions_by_bond,
            truncation_max_error = entry.truncation.max_error,
            krylov_all_converged = entry.krylov.all_converged,
            krylov_max_error_estimate = entry.krylov.max_error_estimate,
            krylov_num_operations = entry.krylov.num_operations,
            krylov_num_iterations = entry.krylov.num_iterations,
            krylov_local_updates = entry.krylov.local_updates,
        ) for entry in entries
    ]
end

function thermal_diagnostics_summary(history, maximum_link_dimensions_by_bond)
    return (;
        steps = length(history),
        max_link_dimension = maximum(
            maximum_link_dimensions_by_bond; init = 1
        ),
        maximum_link_dimensions_by_bond,
        truncation_max_error = maximum(
            (entry.max_truncation_error for entry in history); init = 0.0
        ),
        krylov_all_converged = all(
            entry.krylov_all_converged for entry in history
        ),
        krylov_max_error_estimate = maximum(
            (entry.krylov_max_error_estimate for entry in history);
            init = 0.0,
        ),
        krylov_num_operations = sum(
            entry.krylov_num_operations for entry in history; init = 0
        ),
        krylov_num_iterations = sum(
            entry.krylov_num_iterations for entry in history; init = 0
        ),
        krylov_local_updates = sum(
            entry.krylov_local_updates for entry in history; init = 0
        ),
    )
end

function source_sha256(path)
    return bytes2hex(sha256(read(path)))
end

function checkpoint_identity(request)
    checkpoint = request.checkpoint
    return CheckpointIdentity(;
        request_sha256 = bytes2hex(sha256(request.raw)),
        input_payload_sha256 = request.payload_digest,
        bath_sha256 = request.bath_sha256,
        solver_settings = Dict(
            "beta" => request.beta,
            "tau" => request.tau,
            "time_step" => request.settings.time_step,
            "cutoff" => request.settings.cutoff,
            "maxdim" => request.settings.maxdim,
            "krylov_expansion_dim" =>
                request.settings.krylov_expansion_dim,
        ),
        source_hashes = checkpoint["source_hashes"],
        project_toml_sha256 = checkpoint["project_toml_sha256"],
        manifest_toml_sha256 = checkpoint["manifest_toml_sha256"],
        julia_version = string(VERSION),
        itensors_version = string(Base.pkgversion(ITensors)),
        itensormps_version = string(Base.pkgversion(ITensorMPS)),
        hdf5_version = string(Base.pkgversion(HDF5)),
        checkpoint_schema = checkpoint["checkpoint_schema"],
        writer_version = checkpoint["writer_version"],
    )
end

function make_output(request, result, profiling)
    settings = request.settings
    active_project = Base.active_project()
    active_project === nothing &&
        error("Julia has no active project")
    active_project = abspath(active_project)
    manifest = joinpath(dirname(active_project), "Manifest.toml")
    isfile(manifest) || error("active Julia project has no Manifest.toml")
    return (;
        schema_version = RUNNER_SCHEMA_VERSION,
        input_sha256 = bytes2hex(sha256(request.raw)),
        input_payload_sha256 = request.payload_digest,
        solver = (;
            name = "finite_bath_mps",
            settings = (;
                time_step = settings.time_step,
                cutoff = settings.cutoff,
                maxdim = settings.maxdim,
                krylov_expansion_dim = settings.krylov_expansion_dim,
                bath_representation = request.bath_representation,
                chain_mapping_sha256 = request.mapping_sha256,
            ),
        ),
        tau = result.tau,
        observables = (;
            n_d = result.n_d,
            double_occupancy = result.double_occupancy,
            G_up = result.G_up,
            G_down = result.G_dn,
        ),
        diagnostics = (;
            finite = true,
            profiling,
            log_partition = result.diagnostics.log_partition,
            thermal_log_norm = result.diagnostics.thermal_log_norm,
            thermal_max_link_dimension =
                result.diagnostics.thermal_max_link_dimension,
            maximum_link_dimensions_by_bond =
                result.diagnostics.maximum_link_dimensions_by_bond,
            thermal = thermal_diagnostics_summary(
                result.thermal_state.diagnostics.step_history,
                result.thermal_state.diagnostics.maximum_link_dimensions_by_bond,
            ),
            krylov_expansion_dim = settings.krylov_expansion_dim,
            expansion_policy =
                settings.krylov_expansion_dim == 0 ?
                "tdvp_only" : "explicit_global_krylov",
            bath_representation = request.bath_representation,
            chain_mapping_sha256 = request.mapping_sha256,
            green_up = branch_diagnostics(result.diagnostics.green_up),
            green_down = branch_diagnostics(result.diagnostics.green_dn),
            disclaimer = result.diagnostics.disclaimer,
        ),
        provenance = (;
            runner = "finite_bath_mps_runner",
            runner_version = RUNNER_VERSION,
            julia_version = string(VERSION),
            itensors_version = string(Base.pkgversion(ITensors)),
            itensormps_version = string(Base.pkgversion(ITensorMPS)),
            active_project_path = active_project,
            manifest_path = manifest,
            project_toml_sha256 = source_sha256(active_project),
            manifest_toml_sha256 = source_sha256(manifest),
            runner_source_sha256 = source_sha256(@__FILE__),
            checkpoint_source_sha256 =
                source_sha256(joinpath(@__DIR__, "finite_bath_checkpoint.jl")),
            purification_source_sha256 =
                source_sha256(joinpath(@__DIR__, "finite_bath_purification.jl")),
            observables_source_sha256 =
                source_sha256(joinpath(@__DIR__, "finite_bath_observables.jl")),
            model_definition_sha256 =
                source_sha256(joinpath(@__DIR__, "..", "model.json")),
            chain_mapping_source_sha256 =
                source_sha256(joinpath(@__DIR__, "..", "chain_mapping.py")),
            bath_artifact_file_sha256 =
                String(request.payload["bath_artifact_file_sha256"]),
            bath_representation = request.bath_representation,
            chain_mapping_sha256 = request.mapping_sha256,
            krylov_expansion_dim = settings.krylov_expansion_dim,
            expansion_policy =
                settings.krylov_expansion_dim == 0 ?
                "tdvp_only" : "explicit_global_krylov",
        ),
    )
end

function atomic_write_json(path, value)
    directory = dirname(abspath(path))
    isdir(directory) || throw(ArgumentError("output directory does not exist"))
    temporary, io = mktemp(directory; cleanup = false)
    published = false
    try
        JSON3.write(io, value)
        write(io, '\n')
        flush(io)
        ccall(:fsync, Cint, (Cint,), fd(io)) == 0 ||
            error("fsync failed for temporary result")
        close(io)
        Base.Filesystem.rename(temporary, path)
        published = true
        directory_fd = ccall(:open, Cint, (Cstring, Cint), directory, 0)
        directory_fd >= 0 || error("cannot open output directory for fsync")
        try
            ccall(:fsync, Cint, (Cint,), directory_fd) == 0 ||
                error("fsync failed for output directory")
        finally
            ccall(:close, Cint, (Cint,), directory_fd)
        end
    finally
        isopen(io) && close(io)
        !published && ispath(temporary) && rm(temporary; force = true)
    end
    return nothing
end

function main(args = ARGS)
    length(args) == 3 ||
        throw(
            ArgumentError(
                "usage: finite_bath_mps_runner.jl " *
                "INPUT.json OUTPUT.json CHECKPOINT_ROOT"
            ),
        )
    input_path, output_path, checkpoint_root = abspath.(args)
    println("Reading validated MPS request: $input_path")
    flush(stdout)
    request_started = time_ns()
    request = read_request(input_path)
    identity = checkpoint_identity(request)
    current_path = joinpath(checkpoint_root, "current.json")
    resume =
        ispath(current_path) || islink(current_path) ?
        load_current_checkpoint(checkpoint_root, identity) : nothing
    install_cooperative_shutdown_handlers()
    request_finished = time_ns()
    println(
        "Running finite-bath MPS: n_bath=$(length(request.parameters.epsilon)), " *
        "beta=$(request.beta), tau_points=$(length(request.tau)), " *
        "resuming=$(resume !== nothing)",
    )
    flush(stdout)
    settings = request.settings
    shutdown_checkpoint_published = Ref(false)
    checkpoint_manager = function (psi, state)
        cooperative_shutdown_requested() || return nothing
        completed_steps =
            state.evolution_state === nothing ?
            0 : state.evolution_state.completed_steps
        write_checkpoint_generation(
            checkpoint_root,
            identity,
            completed_steps,
            psi,
            state,
        )
        shutdown_checkpoint_published[] = true
        return nothing
    end
    stop_requested = function ()
        return cooperative_shutdown_requested() &&
               shutdown_checkpoint_published[]
    end
    result = try
        finite_bath_observables(
            request.parameters;
            beta = request.beta,
            tau = request.tau,
            time_step = settings.time_step,
            cutoff = settings.cutoff,
            maxdim = settings.maxdim,
            krylov_expansion_dim = settings.krylov_expansion_dim,
            progress = true,
            checkpoint_manager,
            resume,
            stop_requested,
        )
    catch error
        if error isa ObservableInterrupted
            load_current_checkpoint(checkpoint_root, identity)
            println(
                "Published validated MPS checkpoint; continuation required"
            )
            flush(stdout)
            return CONTINUATION_EXIT_CODE
        end
        rethrow()
    end
    evolution_finished = time_ns()
    base_profile = (;
        phase_timings_seconds = (;
            request_validation =
                (request_finished - request_started) / 1.0e9,
            context_and_evolution =
                (evolution_finished - request_finished) / 1.0e9,
            result_serialization = 0.0,
        ),
        julia_threads = Threads.nthreads(),
        blas_threads = BLAS.get_num_threads(),
        blas_vendor = string(BLAS.vendor()),
        julia_version = string(VERSION),
        peak_rss_bytes = Sys.maxrss(),
        actual_mpo_link_dimensions =
            result.diagnostics.mpo_link_dimensions,
    )
    assembly_started = time_ns()
    output = make_output(request, result, base_profile)
    assembly_finished = time_ns()
    profiling = merge(
        base_profile,
        (;
            phase_timings_seconds = merge(
                base_profile.phase_timings_seconds,
                (;
                    result_serialization =
                        (assembly_finished - assembly_started) / 1.0e9,
                ),
            ),
        ),
    )
    output = make_output(request, result, profiling)
    validate_finite_tree(output)
    atomic_write_json(output_path, output)
    println("Published validated MPS result: $output_path")
    flush(stdout)
    return 0
end

if abspath(PROGRAM_FILE) == abspath(@__FILE__)
    exit(main())
end
