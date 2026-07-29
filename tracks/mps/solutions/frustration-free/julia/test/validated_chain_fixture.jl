isdefined(Main, :validate_chain_mapping_artifact) ||
    include(joinpath(@__DIR__, "..", "finite_bath_mps_runner.jl"))

function _fixture_semicircular_coefficients(n_bath, gamma, bandwidth)
    epsilon = [
        bandwidth * cos(k * pi / (n_bath + 1)) for k in 1:n_bath
    ]
    coupling = [
        sqrt(
            gamma * bandwidth / (n_bath + 1) *
            sin(k * pi / (n_bath + 1))^2,
        ) for k in 1:n_bath
    ]
    return epsilon, coupling
end

function _fixture_bath_artifact(n_bath, gamma, bandwidth)
    epsilon, coupling = _fixture_semicircular_coefficients(
        n_bath, gamma, bandwidth
    )
    grid = [-1.0, 0.0, 1.0]
    width = bandwidth / (n_bath + 1)
    model = authoritative_model_definition()
    convention_names = (
        "hybridization",
        "quadrature",
        "target_continuum",
        "ordering",
        "epsilon",
        "V_squared",
    )
    payload = Dict(
        "schema_version" => 2,
        "parameters" => Dict(
            "gamma" => gamma,
            "bandwidth" => bandwidth,
            "n_bath" => n_bath,
        ),
        "conventions" => Dict(
            name => deepcopy(model["conventions"][name])
            for name in convention_names
        ),
        "provenance" => Dict(
            "module" => "bath",
            "module_version" => "1.0.0",
            "python_version" => "3.12.13",
            "numpy_version" => "2.5.1",
            "schema_version" => 2,
        ),
        "epsilon" => epsilon,
        "V" => coupling,
        "frequency_grid" => grid,
        "target_continuum_hybridization" => [
            abs(omega) <= bandwidth ?
            gamma * sqrt(max(0.0, 1 - (omega / bandwidth)^2)) : 0.0
            for omega in grid
        ],
        "broadening" => Dict(
            "kernel" => "normalized_gaussian",
            "width" => width,
            "width_rule" => "bandwidth / (n_bath + 1)",
            "interpretation" =>
                "broadened finite-bath realization; not the fitted continuum",
        ),
        "broadened_finite_bath_hybridization" => [
            pi * sum(
                coupling[index]^2 *
                exp(-0.5 * ((omega - epsilon[index]) / width)^2) /
                (sqrt(2pi) * width)
                for index in eachindex(epsilon)
            ) for omega in grid
        ],
    )
    digest = bytes2hex(sha256(codeunits(canonical_artifact_json(payload))))
    return Dict("payload" => payload, "sha256" => digest)
end

function _fixture_reorthogonalize(vector, columns)
    result = copy(vector)
    for _ in 1:2, column in columns
        result .-= dot(column, result) .* column
    end
    return result
end

function _fixture_canonical_deflation(columns, tolerance, size)
    for coordinate in 1:size
        candidate = zeros(size)
        candidate[coordinate] = 1.0
        candidate = _fixture_reorthogonalize(candidate, columns)
        candidate_norm = norm(candidate)
        if candidate_norm > tolerance
            candidate ./= candidate_norm
            first = findfirst(value -> abs(value) > tolerance, candidate)
            candidate[first] < 0 && (candidate .*= -1)
            return candidate
        end
    end
    error("fixture canonical deflation could not complete the basis")
end

function _fixture_lanczos(epsilon, coupling)
    size = length(epsilon)
    tolerance =
        64 * eps(Float64) * max(1.0, norm(epsilon, Inf)) * size
    lambda = norm(coupling)
    if iszero(lambda)
        return (
            Matrix{Float64}(I, size, size),
            Matrix(Diagonal(epsilon)),
            lambda,
            size == 1 ? Int[] : collect(0:(size - 2)),
            tolerance,
        )
    end

    columns = [coupling / lambda]
    boundaries = Int[]
    previous_beta = 0.0
    while length(columns) < size
        index = length(columns)
        current = columns[index]
        alpha = dot(current, epsilon .* current)
        residual = epsilon .* current .- alpha .* current
        index > 1 &&
            (residual .-= previous_beta .* columns[index - 1])
        residual = _fixture_reorthogonalize(residual, columns)
        beta = norm(residual)
        if beta > tolerance
            push!(columns, residual / beta)
            previous_beta = beta
        else
            push!(boundaries, index - 1)
            push!(
                columns,
                _fixture_canonical_deflation(
                    columns, tolerance, size
                ),
            )
            previous_beta = 0.0
        end
    end

    Q = reduce(hcat, columns)
    transformed = Q' * Matrix(Diagonal(epsilon)) * Q
    transformed = (transformed + transformed') / 2
    validation_tolerance = 4 * tolerance
    for index in 1:(size - 1)
        index - 1 in boundaries && continue
        value = transformed[index, index + 1]
        value >= -validation_tolerance ||
            error("fixture Lanczos produced a negative hopping")
        if value < 0
            boundary_position =
                findfirst(boundary -> boundary > index - 1, boundaries)
            block_end =
                boundary_position === nothing ?
                size : boundaries[boundary_position] + 1
            Q[:, (index + 1):block_end] .*= -1
            transformed = Q' * Matrix(Diagonal(epsilon)) * Q
            transformed = (transformed + transformed') / 2
        end
    end
    return Q, transformed, lambda, boundaries, tolerance
end

function _fixture_chain_mapping_artifact(bath_artifact)
    epsilon = Float64.(bath_artifact["payload"]["epsilon"])
    coupling = Float64.(bath_artifact["payload"]["V"])
    n_bath = length(epsilon)
    Q, transformed, lambda, boundaries, tolerance =
        _fixture_lanczos(epsilon, coupling)
    diagnostics =
        fixed_order_chain_mapping_diagnostics(epsilon, coupling, Q, lambda)
    boundary_set = Set(boundaries)
    payload = Dict(
        "schema_version" => 1,
        "source_bath_sha256" => bath_artifact["sha256"],
        "source_bath_schema_version" =>
            bath_artifact["payload"]["schema_version"],
        "n_bath" => n_bath,
        "representation" => "finite_chain",
        "lambda" => lambda,
        "Q" => [collect(Q[row, :]) for row in 1:n_bath],
        "chain_onsite" => collect(diag(transformed)),
        "chain_hopping" => [
            index - 1 in boundary_set ?
            0.0 : abs(transformed[index, index + 1])
            for index in 1:(n_bath - 1)
        ],
        "deflation_boundaries" => boundaries,
        "conventions" => deepcopy(CHAIN_MAPPING_CONVENTIONS),
        "numerics" => Dict(
            "algorithm" => "two-pass fully reorthogonalized Lanczos",
            "breakdown_tolerance" => tolerance,
            "breakdown_tolerance_rule" => CHAIN_MAPPING_TOLERANCE_RULE,
            "orthogonality_max_error" =>
                diagnostics["orthogonality_max_error"],
            "off_tridiagonal_max_abs" =>
                diagnostics["off_tridiagonal_max_abs"],
            "coupling_max_error" => diagnostics["coupling_max_error"],
        ),
        "provenance" => deepcopy(CHAIN_MAPPING_PROVENANCE),
    )
    digest = bytes2hex(sha256(codeunits(canonical_artifact_json(payload))))
    artifact = Dict("payload" => payload, "sha256" => digest)
    return artifact, canonical_chain_mapping_json(artifact)
end

function validated_chain_fixture(; n_bath = 1, gamma = 0.1, bandwidth = 1.0)
    n_bath isa Integer && !(n_bath isa Bool) && n_bath > 0 ||
        throw(ArgumentError("n_bath must be a positive integer"))
    gamma = finite_number(gamma, "fixture gamma")
    bandwidth = finite_number(bandwidth, "fixture bandwidth")
    gamma >= 0 || throw(ArgumentError("fixture gamma must be nonnegative"))
    bandwidth > 0 ||
        throw(ArgumentError("fixture bandwidth must be positive"))
    bath_artifact =
        _fixture_bath_artifact(Int(n_bath), gamma, bandwidth)
    model = authoritative_model_definition()
    if gamma == finite_number(model["parameters"]["Gamma"], "model Gamma") &&
       bandwidth == finite_number(model["parameters"]["D"], "model D")
        bath_json = canonical_artifact_json(bath_artifact) * "\n"
        validate_bath_artifact(bath_artifact, bath_json, model)
    end
    mapping_artifact, mapping_json =
        _fixture_chain_mapping_artifact(bath_artifact)
    return validate_chain_mapping_artifact(
        mapping_artifact, mapping_json, bath_artifact
    )
end
