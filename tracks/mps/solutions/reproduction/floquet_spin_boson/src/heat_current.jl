"""Zero-temperature Ohmic spectral density `J(ω)=αω exp(-ω/ωc)`."""
function spectral_density(model::SpinBosonModel, omega::Real)
    isfinite(omega) && omega >= 0 ||
        throw(ArgumentError("spectral-density frequency must be finite and nonnegative"))
    return model.alpha * Float64(omega) *
           exp(-Float64(omega) / model.omega_c)
end

function _validate_current_transform(correlation::AbstractVector,
                                     dt::Real)
    eltype(correlation) <: Complex ||
        throw(ArgumentError("decaying correlation must retain complex values"))
    length(correlation) >= 2 ||
        throw(ArgumentError("current transform requires at least two time samples"))
    all(isfinite, correlation) ||
        throw(ArgumentError("decaying correlation contains non-finite values"))
    isfinite(dt) && dt > 0 ||
        throw(ArgumentError("correlation time step must be finite and positive"))
    return length(correlation)
end

@inline function _current_prefactor(model::SpinBosonModel, omega::Real)
    return 2 * spectral_density(model, omega) * Float64(omega)
end

"""
Blockwise direct quadrature for arbitrary nonnegative frequencies.

This evaluates the one-sided transform with trapezoid endpoint weights without
allocating a `length(frequencies) × length(correlation)` exponential matrix.
"""
function continuous_current_direct!(
    output::AbstractVector,
    frequencies::AbstractVector,
    correlation::AbstractVector,
    dt::Real,
    model::SpinBosonModel;
    block_size::Integer=64)

    length(output) == length(frequencies) ||
        throw(DimensionMismatch("output and frequency grids must have equal length"))
    eltype(output) <: Real ||
        throw(ArgumentError("continuous current output must be real"))
    all(omega -> omega isa Real && isfinite(omega) && omega >= 0,
        frequencies) ||
        throw(ArgumentError("frequency grid must be finite and nonnegative"))
    block_size > 0 || throw(ArgumentError("block_size must be positive"))
    sample_count = _validate_current_transform(correlation, dt)
    step = Float64(dt)

    for block_start in 1:Int(block_size):length(frequencies)
        block_stop = min(length(frequencies),
                         block_start + Int(block_size) - 1)
        @inbounds for frequency_index in block_start:block_stop
            omega = Float64(frequencies[frequency_index])
            transform = 0.5 * ComplexF64(correlation[1])
            for sample in 2:(sample_count - 1)
                transform += ComplexF64(correlation[sample]) *
                             cis(-omega * step * (sample - 1))
            end
            transform += 0.5 * ComplexF64(correlation[end]) *
                         cis(-omega * step * (sample_count - 1))
            output[frequency_index] =
                _current_prefactor(model, omega) * real(step * transform)
        end
    end
    return output
end

"""
FFT-grid continuous heat current using the same trapezoid endpoint rule.

No implicit window is applied. Unsupported window names are rejected so a
plotting choice cannot silently alter the physical linewidth.
"""
function continuous_current_fft(
    correlation::AbstractVector,
    dt::Real,
    model::SpinBosonModel;
    window::Symbol=:none)

    window === :none ||
        throw(ArgumentError("only the recorded :none window is currently supported"))
    sample_count = _validate_current_transform(correlation, dt)
    weighted = ComplexF64.(correlation)
    weighted[1] *= 0.5
    weighted[end] *= 0.5
    transform = Float64(dt) .* fft(weighted)
    positive_count = fld(sample_count, 2) + 1
    omega = Vector{Float64}(undef, positive_count)
    current = Vector{Float64}(undef, positive_count)
    @inbounds for index in 1:positive_count
        frequency = 2π * (index - 1) / (sample_count * Float64(dt))
        omega[index] = frequency
        current[index] =
            _current_prefactor(model, frequency) * real(transform[index])
    end
    return (; omega, current, transform=transform[1:positive_count],
            window, endpoint_rule=:trapezoid)
end

"""One positive-frequency delta contribution to the heat-current measure."""
struct DeltaPeak
    n::Int
    omega::Float64
    c_n::Float64
    spectral_density::Float64
    integrated_weight::Float64
end

"""
Convert asymptotic Fourier coefficients to physical integrated delta weights.

The input uses index `n+1` for harmonic n. Plotting heights are intentionally
absent: the invariant comparison quantity is `integrated_weight`.
"""
function delta_peak_weights(
    model::SpinBosonModel,
    omega_d::Real,
    coefficients::AbstractVector;
    nmax::Integer,
    omega_max::Real,
    weight_tolerance::Real)

    isfinite(omega_d) && omega_d > 0 ||
        throw(ArgumentError("drive frequency must be finite and positive"))
    nmax >= 0 || throw(ArgumentError("nmax must be nonnegative"))
    isfinite(omega_max) && omega_max >= 0 ||
        throw(ArgumentError("omega_max must be finite and nonnegative"))
    isfinite(weight_tolerance) && weight_tolerance >= 0 ||
        throw(ArgumentError("weight_tolerance must be finite and nonnegative"))
    !isempty(coefficients) ||
        throw(ArgumentError("delta coefficient vector cannot be empty"))
    eltype(coefficients) <: Real ||
        throw(ArgumentError("delta coefficients must be real"))
    all(isfinite, coefficients) ||
        throw(ArgumentError("delta coefficients contain non-finite values"))
    minimum(coefficients) >= -64eps(Float64) ||
        throw(ArgumentError("delta coefficients contain a negative weight"))

    peaks = DeltaPeak[]
    last_harmonic = min(Int(nmax), length(coefficients) - 1)
    for n in 1:last_harmonic
        omega = n * Float64(omega_d)
        omega > omega_max && break
        coefficient = max(0.0, Float64(coefficients[n + 1]))
        density = spectral_density(model, omega)
        weight = π * density * omega * coefficient
        weight >= weight_tolerance || continue
        push!(peaks, DeltaPeak(n, omega, coefficient, density, weight))
    end
    return peaks
end

"""
Group drive frequencies whose commensurate Floquet grids have bit-identical dt.

The first occurrence of each dt fixes group order and frequencies retain their
input order. A uniform influence tensor may be reused only inside one group.
"""
function group_frequencies_by_dt(frequencies::AbstractVector,
                                 dt_target::Real)
    isempty(frequencies) &&
        throw(ArgumentError("Fig. 5 frequency grid cannot be empty"))
    groups = NamedTuple{(:dt, :frequencies),
                        Tuple{Float64,Vector{Float64}}}[]
    group_index = Dict{String,Int}()
    for frequency in frequencies
        frequency isa Real && isfinite(frequency) && frequency > 0 ||
            throw(ArgumentError(
                "Fig. 5 frequencies must be finite and positive"))
        grid = period_grid(frequency, dt_target)
        key = bitstring(grid.dt)
        index = get(group_index, key, 0)
        if index == 0
            push!(groups, (dt=grid.dt,
                           frequencies=Float64[frequency]))
            group_index[key] = length(groups)
        else
            push!(groups[index].frequencies, Float64(frequency))
        end
    end
    return groups
end

"""
Integrate a continuous heat-current density and add discrete delta weights.

The continuous grid uses explicit trapezoid weights. Delta peaks enter only
through their invariant integrated weights, never through plotting heights.
"""
function integrated_current(frequencies::AbstractVector,
                            current::AbstractVector,
                            peaks::AbstractVector{<:DeltaPeak};
                            omega_max::Real=last(frequencies))
    length(frequencies) == length(current) ||
        throw(DimensionMismatch(
            "continuous frequency and current grids must have equal length"))
    length(frequencies) >= 2 ||
        throw(ArgumentError(
            "continuous-current integration requires at least two samples"))
    all(value -> value isa Real && isfinite(value), frequencies) ||
        throw(ArgumentError("continuous frequency grid must be finite"))
    all(value -> value isa Real && isfinite(value), current) ||
        throw(ArgumentError("continuous current must be finite"))
    all(diff(Float64.(frequencies)) .> 0) ||
        throw(ArgumentError(
            "continuous frequency grid must be strictly increasing"))
    isfinite(omega_max) &&
        first(frequencies) < omega_max <= last(frequencies) ||
        throw(ArgumentError(
            "integration omega_max must lie inside the continuous grid"))

    continuous = 0.0
    @inbounds for index in 1:(length(frequencies) - 1)
        left_frequency = Float64(frequencies[index])
        left_frequency >= omega_max && break
        right_frequency = Float64(frequencies[index + 1])
        upper_frequency = min(right_frequency, Float64(omega_max))
        fraction = (upper_frequency - left_frequency) /
                   (right_frequency - left_frequency)
        upper_current = Float64(current[index]) +
            fraction *
            (Float64(current[index + 1]) - Float64(current[index]))
        continuous += (upper_frequency - left_frequency) *
            (Float64(current[index]) + upper_current) / 2
    end
    delta = sum(
        peak.integrated_weight for peak in peaks
        if peak.omega <= omega_max;
        init=0.0)
    isfinite(delta) ||
        throw(ArgumentError("delta-current weights must be finite"))
    return (; continuous, delta, total=continuous + delta)
end

"""
Average drive power over one closed, uniformly sampled Floquet period.

Micromotion arrays include the repeated endpoint at T; it is excluded from the
periodic quadrature to avoid double counting phase zero.
"""
function period_averaged_power(drive_power::AbstractVector)
    length(drive_power) >= 2 ||
        throw(ArgumentError(
            "period-averaged power requires phase samples plus closure"))
    all(value -> value isa Real && isfinite(value), drive_power) ||
        throw(ArgumentError("drive power contains non-finite values"))
    isapprox(first(drive_power), last(drive_power);
             atol=128eps(Float64) *
                  max(abs(Float64(first(drive_power))), 1.0),
             rtol=0) ||
        throw(ArgumentError("drive-power samples do not close one period"))
    return sum(Float64, @view drive_power[1:(end - 1)]) /
           (length(drive_power) - 1)
end

function _validate_fig3_config(config::Fig3Config)
    config.mode in (:quick, :validation, :production) ||
        throw(ArgumentError("Fig. 3 mode must be quick, validation, or production"))
    isfinite(config.dt_target) && config.dt_target > 0 ||
        throw(ArgumentError("Fig. 3 target dt must be finite and positive"))
    all(frequency -> isfinite(frequency) && frequency > 0,
        [config.longitudinal_frequencies; config.transversal_frequencies]) ||
        throw(ArgumentError("Fig. 3 frequencies must be finite and positive"))
    config.correlation_lag_steps >= 1 ||
        throw(ArgumentError("Fig. 3 correlation lag count must be positive"))
    2 <= config.tail_count <= config.correlation_lag_steps + 1 ||
        throw(ArgumentError("Fig. 3 tail count is incompatible with correlation length"))
    config.eigensolver_tolerance > 0 ||
        throw(ArgumentError("Fig. 3 eigensolver tolerance must be positive"))
    config.physical_eigenvalue_tolerance > 0 ||
        throw(ArgumentError(
            "Fig. 3 physical eigenvalue tolerance must be positive"))
    config.eigensolver_max_iterations > 0 ||
        throw(ArgumentError("Fig. 3 eigensolver iterations must be positive"))
    for tolerance in (
        config.tail_norm_tolerance,
        config.tail_mean_tolerance,
        config.tail_slope_tolerance,
        config.c0_tolerance,
        config.weight_tolerance)
        isfinite(tolerance) && tolerance >= 0 ||
            throw(ArgumentError("Fig. 3 tolerances must be finite and nonnegative"))
    end
    isfinite(config.omega_max) && config.omega_max > 0 ||
        throw(ArgumentError("Fig. 3 omega_max must be finite and positive"))
    config.nmax >= 0 || throw(ArgumentError("Fig. 3 nmax must be nonnegative"))
    return config
end

function _write_fig3_csv(path::AbstractString, header::AbstractString,
                         rows)
    open(path, "w") do io
        println(io, header)
        for row in rows
            println(io, join(row, ","))
        end
    end
    return path
end

_fig3_json_number(value::Real) =
    isfinite(value) ? repr(Float64(value)) : "null"

function _write_fig3_config(path, config, model, omega_d, grid, chi)
    open(path, "w") do io
        print(io,
            "{\"mode\":\"", config.mode,
            "\",\"drive\":\"", model.drive,
            "\",\"omega_d\":", omega_d,
            ",\"dt_target\":", config.dt_target,
            ",\"dt\":", grid.dt,
            ",\"period\":", grid.T,
            ",\"period_steps\":", grid.M,
            ",\"correlation_lag_steps\":", config.correlation_lag_steps,
            ",\"c0_tolerance\":", config.c0_tolerance,
            ",\"eigensolver_tolerance\":", config.eigensolver_tolerance,
            ",\"physical_eigenvalue_tolerance\":",
            config.physical_eigenvalue_tolerance,
            ",\"bond_dimension\":", chi, "}")
    end
end

function _write_fig3_point(
    point_dir, config, model, omega_d, grid, adapter, steady, reduced,
    micromotion, correlation, decomposition, continuous, peaks, timings,
    reference_metrics)

    mkpath(point_dir)
    _write_fig3_config(
        joinpath(point_dir, "config.json"), config, model, omega_d, grid,
        size(adapter.q, 1))
    JLD2.jldsave(
        joinpath(point_dir, "steady_state.jld2");
        eigenvalue=steady.eigenvalue,
        right_vector=steady.right_vector,
        left_vector=steady.left_vector,
        reduced_density_matrix=reduced.density_matrix,
        right_residual=steady.right_residual,
        left_residual=steady.left_residual)

    spectrum_rows = Any[
        (1, real(steady.eigenvalue), imag(steady.eigenvalue),
         abs(steady.eigenvalue))]
    if !isnothing(steady.subleading_eigenvalue)
        value = steady.subleading_eigenvalue
        push!(spectrum_rows, (2, real(value), imag(value), abs(value)))
    end
    _write_fig3_csv(
        joinpath(point_dir, "floquet_spectrum.csv"),
        "index,real,imag,modulus", spectrum_rows)

    _write_fig3_csv(
        joinpath(point_dir, "micromotion.csv"),
        "phase,time,sigma_x,sigma_y,sigma_z,system_energy,drive_power",
        ((index - 1, (index - 1) * grid.dt,
          micromotion.sigma_x[index], micromotion.sigma_y[index],
          micromotion.sigma_z[index], micromotion.system_energy[index],
          micromotion.drive_power[index])
         for index in eachindex(micromotion.phase_states)))
    _write_fig3_csv(
        joinpath(point_dir, "correlation.csv"),
        "lag,time,real,imag",
        ((index - 1, (index - 1) * grid.dt, real(correlation[index]),
          imag(correlation[index])) for index in eachindex(correlation)))
    _write_fig3_csv(
        joinpath(point_dir, "correlation_decomposition.csv"),
        "lag,time,asym_real,asym_imag,decay_real,decay_imag",
        ((index - 1, (index - 1) * grid.dt,
          real(decomposition.c_asym[index]), imag(decomposition.c_asym[index]),
          real(decomposition.c_decay[index]), imag(decomposition.c_decay[index]))
         for index in eachindex(correlation)))
    _write_fig3_csv(
        joinpath(point_dir, "continuous_heat_current.csv"),
        "omega,current",
        zip(continuous.omega, continuous.current))
    _write_fig3_csv(
        joinpath(point_dir, "delta_peaks.csv"),
        "n,omega,c_n,spectral_density,integrated_weight",
        ((peak.n, peak.omega, peak.c_n, peak.spectral_density,
          peak.integrated_weight) for peak in peaks))

    open(joinpath(point_dir, "diagnostics.json"), "w") do io
        print(io,
            "{\"leading_eigenvalue_real\":",
            _fig3_json_number(real(steady.eigenvalue)),
            ",\"leading_eigenvalue_imag\":",
            _fig3_json_number(imag(steady.eigenvalue)),
            ",\"right_residual\":", _fig3_json_number(steady.right_residual),
            ",\"left_residual\":", _fig3_json_number(steady.left_residual),
            ",\"spectral_gap\":", _fig3_json_number(steady.spectral_gap),
            ",\"trace_real\":", _fig3_json_number(real(reduced.trace)),
            ",\"trace_imag\":", _fig3_json_number(imag(reduced.trace)),
            ",\"hermiticity_error\":",
            _fig3_json_number(reduced.hermiticity_error),
            ",\"minimum_eigenvalue\":",
            _fig3_json_number(reduced.minimum_eigenvalue),
            ",\"augmented_closure\":",
            _fig3_json_number(micromotion.augmented_closure),
            ",\"reduced_closure\":",
            _fig3_json_number(micromotion.reduced_closure),
            ",\"tail_norm\":",
            _fig3_json_number(decomposition.diagnostics.tail_norm),
            ",\"tail_mean_real\":",
            _fig3_json_number(real(decomposition.diagnostics.tail_mean)),
            ",\"tail_mean_imag\":",
            _fig3_json_number(imag(decomposition.diagnostics.tail_mean)),
            ",\"tail_slope\":",
            _fig3_json_number(decomposition.diagnostics.tail_slope),
            ",\"c0_error\":",
            _fig3_json_number(abs(correlation[1] - 1)),
            ",\"reference_max_error\":",
            isnothing(reference_metrics) ? "null" :
                _fig3_json_number(reference_metrics.max_error),
            ",\"reference_rmse\":",
            isnothing(reference_metrics) ? "null" :
                _fig3_json_number(reference_metrics.rmse), "}")
    end
    open(joinpath(point_dir, "timing.json"), "w") do io
        print(io,
            "{\"steady_state_seconds\":", timings.steady_state,
            ",\"micromotion_seconds\":", timings.micromotion,
            ",\"correlation_seconds\":", timings.correlation,
            ",\"transform_seconds\":", timings.transform,
            ",\"total_seconds\":", timings.total, "}")
    end
    return point_dir
end

function _run_fig3_point(config::Fig3Config, output_dir::AbstractString,
                         drive::Symbol, omega_d::Float64,
                         adapter_provider::Function;
                         resume::Bool,
                         parallel_mode::Symbol,
                         reference_provider,
                         warm_start::Union{Nothing,FloquetWarmStart}=nothing)
    point_started = time_ns()
    model = SpinBosonModel(drive=drive)
    grid = period_grid(omega_d, config.dt_target)
    adapter = adapter_provider(model, grid.dt)
    adapter isa UniformIFAdapter ||
        throw(ArgumentError("Fig. 3 adapter provider must return UniformIFAdapter"))
    floquet = FloquetOperator(adapter, model, omega_d, grid.M, grid.dt)
    initial_system = ComplexF64[0.5, 0, 0, 0.5]
    initial = kron(initial_system, ComplexF64.(adapter.v_right))

    started = time_ns()
    steady = solve_floquet_steady_state(
        floquet;
        tolerance=config.eigensolver_tolerance,
        physical_eigenvalue_tolerance=config.physical_eigenvalue_tolerance,
        max_iterations=config.eigensolver_max_iterations,
        initial_vector=isnothing(warm_start) ? initial : nothing,
        warm_start,
        exact_dt=isnothing(warm_start) ? nothing : grid.dt,
        q_identity=isnothing(warm_start) ? nothing :
            uniform_if_key(adapter.metadata))
    steady.converged ||
        throw(ErrorException("Fig. 3 Floquet steady-state solver did not converge"))
    steady = normalize_floquet_trace(steady, adapter.v_left)
    steady_seconds = (time_ns() - started) / 1e9
    reduced = reduce_system_state(steady.right_vector, adapter)

    started = time_ns()
    micromotion = micromotion_states(
        floquet, steady.right_vector, adapter.v_left, model;
        omega_d, exact_dt=grid.dt)
    micromotion_seconds = (time_ns() - started) / 1e9

    correlation = zeros(ComplexF64, config.correlation_lag_steps + 1)
    point_dir = joinpath(output_dir, String(drive), string(omega_d))
    checkpoint_path = joinpath(point_dir, "correlation.checkpoint.jld2")
    config_hash = bytes2hex(sha256(
        string(uniform_if_key(adapter.metadata), "|", drive, "|", omega_d,
               "|", grid.dt, "|", config.correlation_lag_steps, "|",
               bitstring(real(steady.eigenvalue)), "|",
               bitstring(imag(steady.eigenvalue)))))
    started = time_ns()
    floquet_correlation_threaded!(
        correlation, floquet, micromotion.phase_states,
        model.coupling_operator, adapter.v_left;
        config_hash, checkpoint_path, batch_size=max(1, Threads.nthreads()),
        resume=(resume && isfile(checkpoint_path)),
        parallel_mode,
        period_eigenvalue=steady.eigenvalue)
    correlation_seconds = (time_ns() - started) / 1e9
    c0_error = abs(correlation[1] - 1)
    c0_error <= config.c0_tolerance ||
        throw(ArgumentError(
            "Fig. 3 C(0) disagrees with <sigma_z^2>=1 by $c0_error"))

    started = time_ns()
    signal = micromotion.sigma_z[1:grid.M]
    decomposition = decompose_correlation(
        correlation, signal;
        tail_count=config.tail_count,
        tail_norm_tolerance=config.tail_norm_tolerance,
        tail_mean_tolerance=config.tail_mean_tolerance,
        tail_slope_tolerance=config.tail_slope_tolerance)
    reference_metrics = nothing
    continuous = if isnothing(reference_provider)
        continuous_current_fft(decomposition.c_decay, grid.dt, model)
    else
        reference = reference_provider(drive, omega_d)
        hasproperty(reference, :omega) && hasproperty(reference, :current) ||
            throw(ArgumentError(
                "Fig. 3 reference provider must return omega and current"))
        expected_grid = fig3_reference_grid()
        length(reference.omega) == length(expected_grid) &&
            reference.omega == expected_grid ||
            throw(ArgumentError("Fig. 3 reference frequency grid is not exact"))
        length(reference.current) == length(expected_grid) ||
            throw(ArgumentError("Fig. 3 reference current shape is invalid"))
        all(isfinite, reference.current) ||
            throw(ArgumentError("Fig. 3 reference current contains non-finite values"))
        current = zeros(Float64, length(expected_grid))
        continuous_current_direct!(
            current, expected_grid, decomposition.c_decay, grid.dt, model)
        difference = current .- reference.current
        reference_metrics = (
            max_error=maximum(abs, difference),
            rmse=sqrt(sum(abs2, difference) / length(difference)))
        (; omega=expected_grid, current, window=:none,
           endpoint_rule=:trapezoid)
    end
    peaks = delta_peak_weights(
        model, omega_d, decomposition.delta_coefficients;
        nmax=config.nmax, omega_max=config.omega_max,
        weight_tolerance=config.weight_tolerance)
    transform_seconds = (time_ns() - started) / 1e9
    timings = (
        steady_state=steady_seconds,
        micromotion=micromotion_seconds,
        correlation=correlation_seconds,
        transform=transform_seconds,
        total=(time_ns() - point_started) / 1e9)
    _write_fig3_point(
        point_dir, config, model, omega_d, grid, adapter, steady, reduced,
        micromotion, correlation, decomposition, continuous, peaks, timings,
        reference_metrics)
    println("Fig. 3 point ready: drive=", drive, " omega_d=", omega_d,
            " M=", grid.M, " χ=", size(adapter.q, 1))
    flush(stdout)
    next_warm_start = FloquetWarmStart(
        steady.right_vector, grid.dt, uniform_if_key(adapter.metadata),
        floquet.layout)
    return (; drive, omega_d, grid, steady, micromotion, decomposition,
            continuous, peaks, reference_metrics, next_warm_start,
            warm_start_used=!isnothing(warm_start))
end

"""
Run all configured Fig. 3 points through the augmented Floquet pipeline.

`adapter_provider(model, exact_dt)` is responsible for exact-dt cache reuse.
The function never substitutes energy balance for the two-time correlation.
"""
function run_fig3(
    config::Fig3Config,
    output_dir::AbstractString;
    adapter_provider::Function,
    resume::Bool=false,
    parallel_mode::Symbol=:phases,
    reference_provider=nothing)

    _validate_fig3_config(config)
    parallel_mode in (:phases, :none) ||
        throw(ArgumentError("Fig. 3 supports only phase or no parallelism"))
    results = Dict{Tuple{Symbol,Float64},Any}()
    for (drive, frequencies) in (
        (:longitudinal, config.longitudinal_frequencies),
        (:transversal, config.transversal_frequencies))
        for omega_d in frequencies
            point = _run_fig3_point(
                config, output_dir, drive, Float64(omega_d), adapter_provider;
                resume, parallel_mode, reference_provider)
            results[(drive, Float64(omega_d))] = point
        end
    end
    return results
end

function _validate_fig5_config(config::Fig5Config)
    config.mode in (:quick, :validation, :production) ||
        throw(ArgumentError("Fig. 5 mode must be quick, validation, or production"))
    isempty(config.frequencies) &&
        throw(ArgumentError("Fig. 5 frequency grid cannot be empty"))
    all(frequency -> isfinite(frequency) && frequency > 0,
        config.frequencies) ||
        throw(ArgumentError("Fig. 5 frequencies must be finite and positive"))
    issorted(config.frequencies) ||
        throw(ArgumentError("Fig. 5 frequencies must be sorted"))
    length(unique(config.frequencies)) == length(config.frequencies) ||
        throw(ArgumentError("Fig. 5 frequencies must be unique"))
    config.energy_balance_tolerance >= 0 &&
        isfinite(config.energy_balance_tolerance) ||
        throw(ArgumentError("Fig. 5 balance tolerance must be nonnegative"))
    config.energy_balance_floor > 0 && isfinite(config.energy_balance_floor) ||
        throw(ArgumentError("Fig. 5 balance floor must be positive"))
    _validate_fig3_config(_fig3_config(config))
    sample_count = config.correlation_lag_steps + 1
    for frequency in config.frequencies
        exact_dt = period_grid(frequency, config.dt_target).dt
        fft_omega_max =
            2π * fld(sample_count, 2) / (sample_count * exact_dt)
        config.omega_max <= fft_omega_max ||
            throw(ArgumentError(
                "Fig. 5 omega_max exceeds the one-sided FFT grid at " *
                "omega_d=$frequency"))
    end
    return config
end

function _fig3_config(config::Fig5Config)
    return Fig3Config(
        mode=config.mode,
        dt_target=config.dt_target,
        longitudinal_frequencies=Float64[],
        transversal_frequencies=Float64[],
        correlation_lag_steps=config.correlation_lag_steps,
        tail_count=config.tail_count,
        tail_norm_tolerance=config.tail_norm_tolerance,
        tail_mean_tolerance=config.tail_mean_tolerance,
        tail_slope_tolerance=config.tail_slope_tolerance,
        c0_tolerance=config.c0_tolerance,
        omega_max=config.omega_max,
        nmax=config.nmax,
        weight_tolerance=config.weight_tolerance,
        eigensolver_tolerance=config.eigensolver_tolerance,
        physical_eigenvalue_tolerance=config.physical_eigenvalue_tolerance,
        eigensolver_max_iterations=config.eigensolver_max_iterations)
end

const _FIG5_SOURCE_FINGERPRINT = Ref{Union{Nothing,String}}(nothing)
const _FIG5_UNIFORMTEMPO_REVISION = installed_uniformtempo_revision()

function _fig5_source_fingerprint()
    cached = _FIG5_SOURCE_FINGERPRINT[]
    isnothing(cached) || return cached
    files = sort(filter(
        path -> endswith(path, ".jl"),
        readdir(@__DIR__; join=true)))
    source = join(
        (read(file, String) for file in files), '\0')
    fingerprint = bytes2hex(sha256(source))
    _FIG5_SOURCE_FINGERPRINT[] = fingerprint
    return fingerprint
end

"""Hash every immutable setting and implementation identity used by Fig. 5."""
function fig5_config_hash(config::Fig5Config,
                          run_identity::AbstractString)
    isempty(run_identity) &&
        throw(ArgumentError("Fig. 5 run identity cannot be empty"))
    fields = (
        config.mode, config.dt_target, config.frequencies,
        config.correlation_lag_steps, config.tail_count,
        config.tail_norm_tolerance, config.tail_mean_tolerance,
        config.tail_slope_tolerance, config.c0_tolerance,
        config.omega_max, config.nmax, config.weight_tolerance,
        config.eigensolver_tolerance, config.physical_eigenvalue_tolerance,
        config.eigensolver_max_iterations,
        config.energy_balance_tolerance, config.energy_balance_floor,
        String(run_identity), string(VERSION),
        _FIG5_UNIFORMTEMPO_REVISION, _fig5_source_fingerprint())
    return bytes2hex(sha256(repr(fields)))
end

function _fig5_reference_value(reference_provider, drive::Symbol,
                               omega_d::Float64,
                               frequencies::Vector{Float64})
    isnothing(reference_provider) && return nothing
    reference = reference_provider(drive)
    hasproperty(reference, :frequencies) && hasproperty(reference, :current) ||
        throw(ArgumentError(
            "Fig. 5 reference provider must return frequencies and current"))
    reference.frequencies == frequencies ||
        throw(ArgumentError("Fig. 5 reference grid does not match scan grid"))
    length(reference.current) == length(frequencies) &&
        all(isfinite, reference.current) ||
        throw(ArgumentError("Fig. 5 reference current shape is invalid"))
    index = findfirst(==(omega_d), frequencies)
    isnothing(index) &&
        throw(ArgumentError("Fig. 5 point is absent from the reference grid"))
    return Float64(reference.current[index])
end

_fig5_json_escape(value::AbstractString) =
    replace(String(value), '\\' => "\\\\", '"' => "\\\"",
            '\n' => "\\n", '\r' => "\\r")

function _fig5_settings_json(config::Fig5Config, exact_dt::Real)
    return string(
        "{\"mode\":\"", config.mode,
        "\",\"dt_target\":", _fig3_json_number(config.dt_target),
        ",\"exact_dt\":", _fig3_json_number(exact_dt),
        ",\"correlation_lag_steps\":", config.correlation_lag_steps,
        ",\"tail_count\":", config.tail_count,
        ",\"tail_norm_tolerance\":",
        _fig3_json_number(config.tail_norm_tolerance),
        ",\"tail_mean_tolerance\":",
        _fig3_json_number(config.tail_mean_tolerance),
        ",\"tail_slope_tolerance\":",
        _fig3_json_number(config.tail_slope_tolerance),
        ",\"c0_tolerance\":", _fig3_json_number(config.c0_tolerance),
        ",\"omega_max\":", _fig3_json_number(config.omega_max),
        ",\"nmax\":", config.nmax,
        ",\"weight_tolerance\":",
        _fig3_json_number(config.weight_tolerance),
        ",\"eigensolver_tolerance\":",
        _fig3_json_number(config.eigensolver_tolerance),
        ",\"physical_eigenvalue_tolerance\":",
        _fig3_json_number(config.physical_eigenvalue_tolerance),
        ",\"eigensolver_max_iterations\":",
        config.eigensolver_max_iterations,
        ",\"energy_balance_tolerance\":",
        _fig3_json_number(config.energy_balance_tolerance),
        ",\"energy_balance_floor\":",
        _fig3_json_number(config.energy_balance_floor), "}")
end

function _fig5_provenance_json(run_identity::AbstractString;
                               q_identity=nothing)
    return string(
        "{\"spectrum_algorithm\":\"two_time_correlation\"",
        ",\"delta_weights\":\"integrated\",\"run_identity\":\"",
        _fig5_json_escape(run_identity),
        "\",\"julia_version\":\"", VERSION,
        "\",\"uniformtempo_revision\":\"",
        _fig5_json_escape(_FIG5_UNIFORMTEMPO_REVISION),
        "\",\"source_fingerprint\":\"", _fig5_source_fingerprint(),
        "\",\"q_identity\":",
        isnothing(q_identity) ? "null" :
            string("\"", _fig5_json_escape(q_identity), "\""), "}")
end

function _fig5_manifest(config_hash, run_identity, config, point, totals, power,
                        balance_error, reference_value)
    reference_error = isnothing(reference_value) ? nothing :
        totals.total - reference_value
    return string(
        "{\"status\":\"ok\",\"config_hash\":\"", config_hash,
        "\",\"cell_id\":\"", point.drive, "-", point.omega_d,
        "\",\"params\":{\"drive\":\"", point.drive,
        "\",\"omega_d\":", _fig3_json_number(point.omega_d),
        "},\"settings\":", _fig5_settings_json(config, point.grid.dt),
        ",\"provenance\":",
        _fig5_provenance_json(
            run_identity; q_identity=point.next_warm_start.q_identity),
        ",\"warm_start_used\":", point.warm_start_used,
        ",\"continuous_current\":", _fig3_json_number(totals.continuous),
        ",\"delta_current\":", _fig3_json_number(totals.delta),
        ",\"total_current\":", _fig3_json_number(totals.total),
        ",\"period_averaged_power\":", _fig3_json_number(power),
        ",\"energy_balance_error\":", _fig3_json_number(balance_error),
        ",\"reference_current\":",
        isnothing(reference_value) ? "null" :
            _fig3_json_number(reference_value),
        ",\"reference_error\":",
        isnothing(reference_error) ? "null" :
            _fig3_json_number(reference_error), "}")
end

function _fig5_failure_manifest(config_hash, run_identity, config,
                                drive::Symbol, omega_d::Real, error)
    exact_dt = period_grid(omega_d, config.dt_target).dt
    return string(
        "{\"status\":\"failed\",\"config_hash\":\"", config_hash,
        "\",\"cell_id\":\"", drive, "-", omega_d,
        "\",\"params\":{\"drive\":\"", drive,
        "\",\"omega_d\":", _fig3_json_number(omega_d),
        "},\"settings\":", _fig5_settings_json(config, exact_dt),
        ",\"provenance\":", _fig5_provenance_json(run_identity),
        ",\"error\":\"",
        _fig5_json_escape(sprint(showerror, error)), "\"}")
end

function _write_fig5_summary(output_dir::AbstractString,
                             config::Fig5Config)
    for drive in (:longitudinal, :transversal)
        path = joinpath(output_dir, "total_current_$(drive).csv")
        open(path, "w") do io
            println(io,
                "omega_d,status,total_current,period_averaged_power,energy_balance_error")
            for omega_d in config.frequencies
                manifest_path = joinpath(
                    output_dir, String(drive), string(omega_d),
                    "manifest.json")
                if !isfile(manifest_path)
                    println(io, omega_d, ",missing,,,")
                    continue
                end
                contents = read(manifest_path, String)
                status = something(
                    match(r"\"status\"\s*:\s*\"([^\"]+)\"", contents),
                    match(r"$^", "")).captures
                status_value = isempty(status) ? "invalid" : status[1]
                function number_field(name)
                    found = match(
                        Regex("\\\"" * name *
                              "\\\"\\s*:\\s*([-+0-9.eE]+)"), contents)
                    return isnothing(found) ? "" : found.captures[1]
                end
                println(io, join((
                    omega_d, status_value,
                    number_field("total_current"),
                    number_field("period_averaged_power"),
                    number_field("energy_balance_error")), ","))
            end
        end
    end
    return output_dir
end

"""
Run a resumable Fig. 5 scan using the frequency-resolved two-time algorithm.

Uniform influence tensors are constructed once per bit-identical dt group.
Warm starts are retained only inside one drive direction and one such group.
"""
function run_fig5(
    config::Fig5Config,
    output_dir::AbstractString;
    adapter_provider::Function,
    run_identity::AbstractString,
    resume::Bool=false,
    parallel_mode::Symbol=:phases,
    reference_provider=nothing)

    _validate_fig5_config(config)
    isempty(run_identity) &&
        throw(ArgumentError("Fig. 5 run identity cannot be empty"))
    parallel_mode in (:frequencies, :phases, :none) ||
        throw(ArgumentError(
            "Fig. 5 supports frequency, phase, or no parallelism"))
    mkpath(output_dir)
    config_hash = fig5_config_hash(config, run_identity)
    pending_by_drive = Dict(
        drive => (resume ?
            pending_fig5_points(
                output_dir, drive, config.frequencies, config_hash) :
            copy(config.frequencies))
        for drive in (:longitudinal, :transversal))
    pending_sets = Dict(
        drive => Set(pending_by_drive[drive])
        for drive in (:longitudinal, :transversal))
    results = Dict{Tuple{Symbol,Float64},Any}()
    fig3_config = _fig3_config(config)
    results_lock = ReentrantLock()
    scan_errors = Pair{Tuple{Symbol,Float64},Any}[]

    function execute_point(drive, omega_d, group_provider, warm_start,
                           point_parallel_mode)
        point_dir = joinpath(
            output_dir, String(drive), string(omega_d))
        mkpath(point_dir)
        manifest_path = joinpath(point_dir, "manifest.json")
        try
            point = _run_fig3_point(
                fig3_config, output_dir, drive, omega_d,
                group_provider;
                resume, parallel_mode=point_parallel_mode,
                reference_provider=nothing, warm_start)
            totals = integrated_current(
                point.continuous.omega,
                point.continuous.current, point.peaks;
                omega_max=config.omega_max)
            power = period_averaged_power(
                point.micromotion.drive_power)
            balance_error = abs(power - totals.total) /
                max(abs(power), abs(totals.total),
                    config.energy_balance_floor)
            balance_error <= config.energy_balance_tolerance ||
                throw(ErrorException(
                    "Fig. 5 energy balance failed at drive=$drive " *
                    "omega_d=$omega_d: $balance_error"))
            reference_value = _fig5_reference_value(
                reference_provider, drive, omega_d,
                config.frequencies)
            save_fig5_manifest(
                manifest_path,
                _fig5_manifest(
                    config_hash, run_identity, config, point, totals, power,
                    balance_error, reference_value))
            value = (
                ; point, totals, power, balance_error,
                reference_value)
            lock(results_lock) do
                results[(drive, omega_d)] = value
            end
            return point.next_warm_start
        catch error
            save_fig5_manifest(
                manifest_path,
                _fig5_failure_manifest(
                    config_hash, run_identity, config,
                    drive, omega_d, error))
            rethrow()
        end
    end

    for group in group_frequencies_by_dt(
            config.frequencies, config.dt_target)
        any_pending = any(
            omega_d in pending_sets[drive]
            for drive in (:longitudinal, :transversal)
            for omega_d in group.frequencies)
        any_pending || continue
        adapter = adapter_provider(
            SpinBosonModel(drive=:longitudinal), group.dt)
        adapter isa UniformIFAdapter ||
            throw(ArgumentError(
                "Fig. 5 adapter provider must return UniformIFAdapter"))
        group_provider = (_, exact_dt) -> begin
            bitstring(Float64(exact_dt)) == bitstring(group.dt) ||
                throw(ArgumentError("Fig. 5 dt group changed unexpectedly"))
            adapter
        end

        if parallel_mode === :frequencies
            jobs = [
                (drive=drive, omega_d=omega_d)
                for drive in (:longitudinal, :transversal)
                for omega_d in group.frequencies
                if omega_d in pending_sets[drive]
            ]
            errors = Pair{Tuple{Symbol,Float64},Any}[]
            errors_lock = ReentrantLock()
            Threads.@threads :static for index in eachindex(jobs)
                job = jobs[index]
                try
                    execute_point(
                        job.drive, job.omega_d, group_provider, nothing, :none)
                catch error
                    lock(errors_lock) do
                        push!(errors, (job.drive, job.omega_d) => error)
                    end
                end
            end
            append!(scan_errors, errors)
            continue
        end

        for drive in (:longitudinal, :transversal)
            warm_start = nothing
            for omega_d in group.frequencies
                omega_d in pending_sets[drive] || continue
                try
                    warm_start = execute_point(
                        drive, omega_d, group_provider, warm_start,
                        parallel_mode)
                catch error
                    push!(scan_errors, (drive, omega_d) => error)
                    warm_start = nothing
                end
            end
        end
    end
    _write_fig5_summary(output_dir, config)
    isempty(scan_errors) ||
        throw(ErrorException(
            "Fig. 5 scan failed at " *
            join(string.(first.(scan_errors)), ", ")))
    return results
end
