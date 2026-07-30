#!/usr/bin/env julia

if length(ARGS) != 2
    println(stderr, "UniformTEMPO input error: expected input JSON path and output JSON path")
    exit(2)
end
if !isfile(ARGS[1])
    println(stderr, "UniformTEMPO input error: input JSON does not exist: $(ARGS[1])")
    exit(2)
end

using JSON3
using KrylovKit
using LinearAlgebra
using OrdinaryDiffEq
using SHA
using Serialization
using UniformTEMPO

const METHOD = "uniform_tempo_floquet_multitime"
const UNIFORM_TEMPO_REVISION = "b76a018c32e5415989761d902b1b0e95f1a337da"

function fail(message::AbstractString)
    println(stderr, "UniformTEMPO input error: " * message)
    exit(2)
end

function required(object, key::Symbol)
    haskey(object, key) || fail("missing input field: $(key)")
    return object[key]
end

function decode_real_matrix(raw, label::AbstractString)
    rows = [Float64.(collect(row)) for row in raw]
    isempty(rows) && fail("$(label) must not be empty")
    width = length(first(rows))
    width > 0 || fail("$(label) must not have empty rows")
    all(length(row) == width for row in rows) ||
        fail("$(label) rows have inconsistent lengths")
    return reduce(vcat, permutedims.(rows))
end

function decode_complex_matrix(raw, label::AbstractString)
    real_part = decode_real_matrix(required(raw, :real), "$(label).real")
    imag_part = decode_real_matrix(required(raw, :imag), "$(label).imag")
    size(real_part) == size(imag_part) ||
        fail("$(label) real and imaginary shapes differ")
    return ComplexF64.(real_part, imag_part)
end

encode_complex(values) = Dict(
    "real" => real.(values),
    "imag" => imag.(values),
    "shape" => collect(size(values)),
)

function finite_complex(values)
    return all(isfinite, real.(values)) && all(isfinite, imag.(values))
end

function validate_hermitian(matrix, label::AbstractString)
    size(matrix, 1) == size(matrix, 2) || fail("$(label) must be square")
    norm(matrix - matrix') <= 1e-10 || fail("$(label) must be Hermitian")
end

function atomic_json_write(path::AbstractString, payload)
    directory = dirname(path)
    mkpath(directory)
    temporary = path * ".tmp-" * string(getpid())
    open(temporary, "w") do io
        JSON3.pretty(io, payload)
        write(io, '\n')
    end
    mv(temporary, path; force=true)
end

function load_or_build_process_tensor(
    coupling,
    dt,
    bcf,
    tolerance;
    auto_nc,
    memory_cutoff,
    truncation,
    cap_rank,
    low_rank_svd,
    max_rank,
    cache_path,
    cache_key,
)
    if cache_path !== nothing && isfile(cache_path)
        record = deserialize(cache_path)
        record isa AbstractDict ||
            fail("process tensor cache record is invalid")
        get(record, :key, nothing) == cache_key ||
            fail("process tensor cache key does not match")
        get(record, :uniform_tempo_revision, nothing) == UNIFORM_TEMPO_REVISION ||
            fail("process tensor cache revision does not match")
        get(record, :system_dimension, nothing) == size(coupling, 1) ||
            fail("process tensor cache dimension does not match")
        cached_dt = get(record, :dt, nothing)
        cached_dt isa Real && isapprox(cached_dt, dt; rtol=1e-13, atol=1e-15) ||
            fail("process tensor cache timestep does not match")
        haskey(record, :process_tensor) ||
            fail("process tensor cache has no tensor")
        return record[:process_tensor], true
    end

    pt = uniTEMPO(
        coupling,
        dt,
        bcf,
        tolerance;
        auto_nc=auto_nc,
        n_c=memory_cutoff,
        truncation=truncation,
        cap_rank=cap_rank,
        low_rank_svd=low_rank_svd,
        max_rank=max_rank,
    )
    if cache_path !== nothing
        mkpath(dirname(cache_path))
        temporary = cache_path * ".tmp-" * string(getpid())
        record = Dict(
            :key => cache_key,
            :uniform_tempo_revision => UNIFORM_TEMPO_REVISION,
            :system_dimension => size(coupling, 1),
            :dt => dt,
            :process_tensor => pt,
        )
        open(temporary, "w") do io
            serialize(io, record)
        end
        mv(temporary, cache_path; force=true)
    end
    return pt, false
end

function main()
    input_path, output_path = ARGS

    input = JSON3.read(read(input_path, String))
    h0 = decode_complex_matrix(required(input, :h0), "h0")
    coupling = decode_complex_matrix(required(input, :coupling), "coupling")
    drive = decode_complex_matrix(required(input, :drive), "drive")
    validate_hermitian(h0, "h0")
    validate_hermitian(coupling, "coupling")
    validate_hermitian(drive, "drive")
    size(h0) == size(coupling) ||
        fail("h0 and coupling dimensions differ")
    size(h0) == size(drive) ||
        fail("h0 and drive dimensions differ")

    model = required(input, :model)
    drive_amplitude = Float64(required(model, :drive_amplitude))
    drive_frequency = Float64(required(model, :drive_frequency))
    drive_frequency > 0 || fail("drive_frequency must be positive")

    bath = required(input, :bath)
    alpha = Float64(required(bath, :alpha))
    cutoff = Float64(required(bath, :cutoff))
    temperature = Float64(required(bath, :temperature))
    alpha >= 0 || fail("alpha must be nonnegative")
    cutoff > 0 || fail("cutoff must be positive")
    temperature == 0 ||
        fail("the current analytic bath correlation supports temperature=0 only")

    controls = required(input, :controls)
    period_steps = Int(required(controls, :steps_per_period))
    tolerance = Float64(required(controls, :tolerance))
    phase_offsets = Int.(collect(required(controls, :phase_offsets)))
    delay_steps = Int(required(controls, :delay_steps))
    auto_nc = Bool(required(controls, :auto_nc))
    memory_cutoff = Int(required(controls, :memory_cutoff))
    low_rank_svd = Bool(required(controls, :low_rank_svd))
    truncation = Symbol(String(required(controls, :truncation)))
    cap_rank = Int(required(controls, :cap_rank))
    max_rank = Int(required(controls, :max_rank))
    pole_count = Int(required(controls, :pole_count))
    pole_tolerance = Float64(required(controls, :pole_tolerance))
    pole_maxiter = Int(required(controls, :pole_maxiter))
    process_tensor_cache_path = if haskey(controls, :process_tensor_cache_path)
        String(controls[:process_tensor_cache_path])
    else
        nothing
    end
    process_tensor_cache_key = if haskey(controls, :process_tensor_cache_key)
        String(controls[:process_tensor_cache_key])
    else
        nothing
    end

    period_steps >= 2 || fail("steps_per_period must be at least two")
    0 < tolerance < 1 || fail("tolerance must lie between zero and one")
    delay_steps >= 1 || fail("delay_steps must be positive")
    memory_cutoff >= 1 || fail("memory_cutoff must be positive")
    cap_rank >= 1 || fail("cap_rank must be positive")
    max_rank >= cap_rank || fail("max_rank must be at least cap_rank")
    pole_count >= 0 || fail("pole_count must be nonnegative")
    pole_tolerance > 0 || fail("pole_tolerance must be positive")
    pole_maxiter >= 1 || fail("pole_maxiter must be positive")
    truncation in (:rel, :abs) || fail("truncation must be rel or abs")
    length(phase_offsets) >= 2 ||
        fail("at least two phase offsets are required")
    length(unique(phase_offsets)) == length(phase_offsets) ||
        fail("phase offsets must be unique")
    all(0 .<= phase_offsets .< period_steps) ||
        fail("phase offsets must lie within one period")
    (process_tensor_cache_path === nothing) ==
        (process_tensor_cache_key === nothing) ||
        fail("process tensor cache path and key must be supplied together")
    process_tensor_cache_key === nothing ||
        occursin(r"^[0-9a-f]{64}$", process_tensor_cache_key) ||
        fail("process tensor cache key must be a SHA-256 digest")

    period = 2π / drive_frequency
    dt = period / period_steps
    h_s(time) = h0 + drive_amplitude * cos(drive_frequency * time) * drive
    bcf(time) = alpha * (cutoff / (1 + im * cutoff * time))^2

    pt, process_tensor_cache_hit = load_or_build_process_tensor(
        coupling,
        dt,
        bcf,
        tolerance;
        auto_nc=auto_nc,
        memory_cutoff=memory_cutoff,
        truncation=truncation,
        cap_rank=cap_rank,
        low_rank_svd=low_rank_svd,
        max_rank=max_rank,
        cache_path=process_tensor_cache_path,
        cache_key=process_tensor_cache_key,
    )
    ptf = floquet_process_tensor(pt, h_s, period)
    extended_floquet_state = steadystate(ptf; return_full=true)
    floquet_state = reshape(
        ptf.v_l * extended_floquet_state,
        size(h0),
    )
    floquet_state ./= tr(floquet_state)
    floquet_transfer = reshape(
        ptf.q,
        size(ptf.q, 1) * size(ptf.q, 2),
        size(ptf.q, 1) * size(ptf.q, 2),
    )
    floquet_transfer_residual = norm(
        floquet_transfer * extended_floquet_state[:] -
        extended_floquet_state[:]
    ) / max(norm(extended_floquet_state), eps())
    transfer_eigenvalues = ComplexF64[]
    transfer_eigenpair_residuals = Float64[]
    if pole_count > 0
        requested = min(pole_count, size(floquet_transfer, 1) - 1)
        values_raw, vectors, _ = eigsolve(
            floquet_transfer,
            requested,
            :LM;
            tol=pole_tolerance,
            maxiter=pole_maxiter,
        )
        order = sortperm(abs.(values_raw); rev=true)
        length(order) >= requested ||
            error("KrylovKit returned fewer transfer poles than requested")
        selected = order[1:requested]
        transfer_eigenvalues = ComplexF64.(values_raw[selected])
        transfer_eigenpair_residuals = [
            norm(
                floquet_transfer * vectors[index] -
                values_raw[index] * vectors[index]
            ) / max(norm(vectors[index]), eps())
            for index in selected
        ]
    end

    micromotion = evolve(pt, extended_floquet_state, period_steps; h_s=h_s)
    extended_after_period = evolve(
        pt,
        extended_floquet_state,
        period_steps;
        h_s=h_s,
        return_full=true,
    )
    fixed_point_residual = norm(
        extended_after_period - extended_floquet_state
    ) / max(norm(extended_floquet_state), eps())

    selected_states = [micromotion[offset + 1] for offset in phase_offsets]
    one_point = [real(tr(coupling * state)) for state in selected_states]
    correlation_records = Vector{Vector{ComplexF64}}()
    for offset in phase_offsets
        extended_phase_state = if offset == 0
            extended_floquet_state
        else
            evolve(
                pt,
                extended_floquet_state,
                offset;
                h_s=h_s,
                return_full=true,
            )
        end
        h_shifted(time) = h_s(time + offset * dt)
        record = two_point_correlations(
            pt,
            extended_phase_state,
            0,
            delay_steps,
            coupling,
            coupling;
            h_s=h_shifted,
        )
        push!(correlation_records, ComplexF64.(record))
    end
    total_correlation = reduce(+, correlation_records) / length(correlation_records)

    trace_error = maximum(abs(tr(state) - 1) for state in selected_states)
    hermiticity_error = maximum(norm(state - state') for state in selected_states)
    minimum_density_eigenvalue = minimum(
        minimum(eigvals(Hermitian((state + state') / 2)))
        for state in selected_states
    )
    finite_complex(floquet_state) || error("non-finite Floquet state")
    finite_complex(total_correlation) || error("non-finite correlation")
    finite_complex(transfer_eigenvalues) || error("non-finite transfer eigenvalue")
    all(isfinite, transfer_eigenpair_residuals) ||
        error("non-finite transfer eigenpair residual")

    manifest_path = joinpath(dirname(Base.active_project()), "Manifest.toml")
    payload = Dict(
        "method" => METHOD,
        "dt" => dt,
        "period_steps" => period_steps,
        "bond_dimension" => bond_dim(pt),
        "floquet_state" => encode_complex(floquet_state),
        "phase_states" => encode_complex(cat(selected_states...; dims=3)),
        "one_point" => one_point,
        "phase_offsets" => phase_offsets,
        "delay" => collect(0:delay_steps) .* dt,
        "correlation" => encode_complex(total_correlation),
        "diagnostics" => Dict(
            "trace_error" => trace_error,
            "hermiticity_error" => hermiticity_error,
            "minimum_density_eigenvalue" => minimum_density_eigenvalue,
            "fixed_point_residual" => fixed_point_residual,
            "floquet_transfer_residual" => floquet_transfer_residual,
        ),
        "julia_version" => string(VERSION),
        "uniform_tempo_revision" => UNIFORM_TEMPO_REVISION,
        "manifest_sha256" => bytes2hex(sha256(read(manifest_path))),
        "process_tensor_cache_hit" => process_tensor_cache_hit,
        "transfer_eigenvalues" => encode_complex(transfer_eigenvalues),
        "transfer_eigenpair_residuals" => transfer_eigenpair_residuals,
        "transfer_dimension" => size(floquet_transfer, 1),
    )
    atomic_json_write(output_path, payload)
end

main()
