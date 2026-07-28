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
                         reference_provider)
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
        max_iterations=config.eigensolver_max_iterations,
        initial_vector=initial)
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
               "|", grid.dt, "|", config.correlation_lag_steps)))
    started = time_ns()
    floquet_correlation_threaded!(
        correlation, floquet, micromotion.phase_states,
        model.coupling_operator, adapter.v_left;
        config_hash, checkpoint_path, batch_size=max(1, Threads.nthreads()),
        resume=(resume && isfile(checkpoint_path)),
        parallel_mode)
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
    return (; drive, omega_d, grid, steady, decomposition, continuous, peaks,
            reference_metrics)
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
