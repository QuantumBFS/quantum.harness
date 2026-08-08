struct METTSResult
    parameters::Dict{Symbol,Any}
    samples::Vector{NamedTuple}
    summary::Dict{Symbol,NamedTuple}
    final_configuration::Matrix{Int}
    final_basis::Symbol
    transition_diagnostics::Vector{NamedTuple}
end

function sanitize_probability_weights(weights::AbstractVector{<:Real}; tolerance=1e-10)
    scale = maximum(abs, weights; init=0.0)
    isfinite(scale) || error("conditional probabilities contain non-finite weights")
    scale > 0 || error("conditional probabilities have zero total weight")
    floor_value = tolerance * scale
    cleaned = Float64[]
    for weight in weights
        weight < -floor_value && error(
            "Boundary-MPS produced a negative conditional weight $weight; increase chi",
        )
        push!(cleaned, max(0.0, Float64(weight)))
    end
    total = sum(cleaned)
    total > 0 || error("conditional probabilities have zero total weight")
    return cleaned ./ total
end




function collapse_basis(
    state::DenseFinitePEPS;
    basis::Symbol,
    chi::Integer,
    rng::AbstractRNG=Random.default_rng(),
)
    projector_positive, projector_negative = collapse_projectors(basis)
    insertions = Dict{CartesianIndex{2},Any}()
    configuration = Matrix{Int}(undef, state.Lx, state.Ly)
    max_boundary_error = 0.0
    minimum_probability = 1.0
    for y in 1:state.Ly, x in 1:state.Lx
        site = CartesianIndex(x, y)
        trial_positive = copy(insertions)
        trial_positive[site] = projector_positive
        trial_negative = copy(insertions)
        trial_negative[site] = projector_negative
        positive_result = boundary_mps_contract(state; chi, insertions=trial_positive)
        negative_result = boundary_mps_contract(state; chi, insertions=trial_negative)
        max_boundary_error = max(
            max_boundary_error,
            positive_result.max_truncation_error,
            negative_result.max_truncation_error,
        )
        probabilities = sanitize_probability_weights(real.([
            positive_result.value,
            negative_result.value,
        ]))
        minimum_probability = min(minimum_probability, probabilities...)
        if rand(rng) < probabilities[1]
            configuration[x, y] = 1
            insertions[site] = projector_positive
        else
            configuration[x, y] = -1
            insertions[site] = projector_negative
        end
    end
    diagnostics = (; basis, max_boundary_error, minimum_probability)
    return configuration, diagnostics
end

function collapse_z_basis(
    state::DenseFinitePEPS;
    chi::Integer,
    rng::AbstractRNG=Random.default_rng(),
)
    return collapse_basis(state; basis=:Z, chi, rng)
end

function collapse_x_basis(
    state::DenseFinitePEPS;
    chi::Integer,
    rng::AbstractRNG=Random.default_rng(),
)
    return collapse_basis(state; basis=:X, chi, rng)
end

function integrated_autocorrelation_time(values::AbstractVector{<:Real})
    sample_count = length(values)
    sample_count <= 2 && return 1.0
    centered = Float64.(values) .- mean(values)
    variance = sum(abs2, centered) / sample_count
    variance == 0 && return 1.0
    max_lag = min(sample_count - 1, max(1, floor(Int, 5sqrt(sample_count))))
    correlation_sum = 0.0
    for lag in 1:max_lag
        covariance = dot(
            @view(centered[1:(sample_count - lag)]),
            @view(centered[(lag + 1):sample_count]),
        ) / (sample_count - lag)
        correlation = covariance / variance
        correlation <= 0 && break
        correlation_sum += correlation
    end
    return max(1.0, 1 + 2correlation_sum)
end

function scalar_sample_summary(values::AbstractVector{<:Real})
    sample_count = length(values)
    sample_count > 0 || throw(ArgumentError("cannot summarize an empty sample"))
    tau = integrated_autocorrelation_time(values)
    effective_samples = sample_count / tau
    if sample_count == 1
        return (;
            mean=Float64(first(values)),
            standard_error=NaN,
            autocorrelation_time=tau,
            effective_samples,
            block_size=1,
            block_count=1,
        )
    end
    block_size = max(1, ceil(Int, tau))
    block_count = fld(sample_count, block_size)
    if block_count >= 2
        block_means = [
            mean(@view values[((block - 1) * block_size + 1):(block * block_size)])
            for block in 1:block_count
        ]
        standard_error = std(block_means) / sqrt(block_count)
    else
        standard_error = std(values) / sqrt(effective_samples)
    end
    return (;
        mean=mean(values),
        standard_error,
        autocorrelation_time=tau,
        effective_samples,
        block_size,
        block_count,
    )
end

function summarize_samples(samples::Vector{<:NamedTuple})
    isempty(samples) && throw(ArgumentError("no METTS samples were recorded"))
    summary = Dict{Symbol,NamedTuple}()
    for field in (:energy, :energy_per_site, :x_magnetization, :z_magnetization, :zz_nearest_neighbor)
        summary[field] = scalar_sample_summary([getproperty(sample, field) for sample in samples])
    end
    correlation_count = length(samples[1].correlations)
    for distance in 1:correlation_count
        key = Symbol("correlation_R", distance)
        summary[key] = scalar_sample_summary([sample.correlations[distance] for sample in samples])
    end
    return summary
end

function initial_configuration(
    Lx::Integer,
    Ly::Integer,
    initial_state::Symbol,
    rng::AbstractRNG,
)
    initial_state === :all_up && return ones(Int, Lx, Ly)
    initial_state === :random && return rand(rng, (-1, 1), Lx, Ly)
    throw(ArgumentError("initial_state must be :all_up or :random"))
end

function validate_metts_parameters(para::AbstractDict)
    para[:D] >= 1 || throw(ArgumentError("D must be positive"))
    para[:chi] >= 1 || throw(ArgumentError("chi must be positive"))
    para[:beta] >= 0 || throw(ArgumentError("beta must be nonnegative"))
    para[:tau] > 0 || throw(ArgumentError("tau must be positive"))
    para[:burn_in] >= 0 || throw(ArgumentError("burn_in must be nonnegative"))
    para[:samples] >= 1 || throw(ArgumentError("samples must be positive"))
    para[:thinning] >= 1 || throw(ArgumentError("thinning must be positive"))
    get(para, :initial_basis, :Z) in (:Z, :X) ||
        throw(ArgumentError("initial_basis must be :Z or :X"))
    return true
end

function run_metts(
    para::Dict{Symbol,Any}=default_metts_parameters();
    Lx::Integer=4,
    Ly::Integer=4,
)
    Lx >= 2 || throw(ArgumentError("Lx must be at least 2"))
    Ly >= 2 || throw(ArgumentError("Ly must be at least 2"))
    validate_metts_parameters(para)
    rng = MersenneTwister(para[:seed])
    configuration = initial_configuration(Lx, Ly, para[:initial_state], rng)
    product_basis = get(para, :initial_basis, :Z)
    samples = NamedTuple[]
    transition_diagnostics = NamedTuple[]
    total_transitions = para[:burn_in] + para[:samples] * para[:thinning]

    for transition in 1:total_transitions
        gamma_lambda_state = product_peps(configuration; basis=product_basis)
        evolution_history = imaginary_time_evolve!(gamma_lambda_state, para)
        peps = DenseFinitePEPS(gamma_lambda_state)
        validate_finite_peps(peps)
        next_basis = isodd(transition) ? :Z : :X

        should_record = transition > para[:burn_in] &&
            (transition - para[:burn_in]) % para[:thinning] == 0
        if should_record
            observables = metts_observables(peps, para)
            sample_index = length(samples) + 1
            max_su_error = isempty(evolution_history) ? 0.0 :
                maximum(record.max_truncation_error for record in evolution_history)
            push!(samples, (;
                sample=sample_index,
                transition,
                product_basis,
                collapse_basis=next_basis,
                max_su_error,
                observables...,
            ))
        end

        configuration, collapse_diagnostics = collapse_basis(
            peps;
            basis=next_basis,
            chi=para[:chi],
            rng,
        )
        product_basis = next_basis
        push!(transition_diagnostics, (; transition, collapse_diagnostics...))
        if get(para, :verbose, 1) > 0
            stage = transition <= para[:burn_in] ? "burn-in" : "sampling"
            println("METTS transition $transition/$total_transitions ($stage), recorded=$(length(samples))")
        end
    end
    return METTSResult(
        copy(para),
        samples,
        summarize_samples(samples),
        configuration,
        product_basis,
        transition_diagnostics,
    )
end
