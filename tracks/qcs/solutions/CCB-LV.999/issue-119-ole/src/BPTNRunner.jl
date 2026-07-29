module BPTNRunner

using LinearAlgebra
using TensorNetworkQuantumSimulator

if !isdefined(parentmodule(@__MODULE__), :OLEProtocol)
    Base.include(parentmodule(@__MODULE__), joinpath(@__DIR__, "OLEProtocol.jl"))
end
using ..OLEProtocol

export norm_diagnostic, run_seed

function norm_diagnostic(normalize_tensors::Bool, stored_norm_sqr = nothing)
    if normalize_tensors
        return (
            available = false,
            defect = NaN,
            reason = "local_tensor_normalization_drops_global_scale",
        )
    end
    isnothing(stored_norm_sqr) &&
        throw(ArgumentError("stored_norm_sqr is required when normalization is disabled"))
    return (
        available = true,
        defect = abs(real(stored_norm_sqr) - 1),
        reason = "available",
    )
end

function _initial_state(protocol, seed_namespace, seed_id, ::Type{T}) where {T}
    bits = basis_bits(seed_namespace, seed_id, protocol.physical_labels)
    bits_by_label = Dict(zip(protocol.physical_labels, bits))
    tnqs_circuit = reduce(vcat, tnqs_layers(protocol))
    graph = build_graph_from_circuit(tnqs_circuit)
    state = tensornetworkstate(
        T,
        vertex -> iszero(bits_by_label[vertex]) ? "↑" : "↓",
        graph,
        "S=1/2",
    )
    return state, bits_by_label
end

function _bp_fixed_point_residual(cache)
    probe = update(cache; maxiter = 1, tolerance = nothing, verbose = false)
    directed_edges = collect(keys(messages(cache)))
    isempty(directed_edges) && return 0.0
    residual = 0.0
    for edge in directed_edges
        previous = message(cache, edge)
        updated = message(probe, edge)
        denominator = norm(previous) * norm(updated)
        iszero(denominator) && return Inf
        fidelity = abs2(dot(previous, updated) / denominator)
        residual += max(0.0, 1 - real(fidelity))
    end
    return residual / length(directed_edges)
end

"""
    run_seed(protocol; ...)

Run one computational-basis OLE sample with the pinned TNQS BP/simple-update
engine. The QASM has already been parsed and validated by `OLEProtocol`.
"""
function run_seed(
    protocol::OLEQASMProtocol;
    seed_namespace::AbstractString,
    seed_id::Integer,
    observable_labels,
    maxdim::Integer,
    cutoff::Real,
    dtype::Type = ComplexF64,
    bp_maxiter::Integer = 25,
    bp_tolerance::Real = dtype === ComplexF32 ? 1.0e-5 : 1.0e-8,
    normalize_tensors::Bool = true,
    progress::Bool = true,
    layer_callback = nothing,
)
    dtype in (ComplexF32, ComplexF64) ||
        throw(ArgumentError("dtype must be ComplexF32 or ComplexF64"))
    maxdim > 0 || throw(ArgumentError("maxdim must be positive"))
    cutoff >= 0 || throw(ArgumentError("cutoff must be nonnegative"))
    bp_maxiter > 0 || throw(ArgumentError("bp_maxiter must be positive"))
    all(in(protocol.physical_labels), observable_labels) ||
        throw(ArgumentError("observable contains a label absent from the active graph"))

    start_ns = time_ns()
    state, bits_by_label = _initial_state(protocol, seed_namespace, seed_id, dtype)
    bp_kwargs = (
        maxiter = Int(bp_maxiter),
        tolerance = Float64(bp_tolerance),
        verbose = false,
    )
    apply_kwargs = (
        maxdim = Int(maxdim),
        cutoff = Float64(cutoff),
        normalize_tensors,
    )
    cache = update(BeliefPropagationCache(state); bp_kwargs...)

    layer_records = NamedTuple[]
    all_errors = Float64[]
    layers = tnqs_layers(protocol)
    for (layer_index, layer) in enumerate(layers)
        layer_start_ns = time_ns()
        cache, errors = apply_gates(
            layer,
            cache;
            apply_kwargs,
            bp_update_kwargs = bp_kwargs,
            verbose = false,
        )
        errors = Float64.(errors)
        append!(all_errors, errors)
        bp_residual = _bp_fixed_point_residual(cache)
        norm_status = normalize_tensors ?
                      norm_diagnostic(true) :
                      norm_diagnostic(false, norm_sqr(cache; alg = "bp"))
        record = (
            layer = layer_index,
            gate_count = length(layer),
            max_bond_dimension = maxvirtualdim(network(cache)),
            max_truncation_error = isempty(errors) ? 0.0 : maximum(errors),
            sum_truncation_error = sum(errors),
            bp_residual,
            bp_converged = isfinite(bp_residual) && bp_residual <= bp_tolerance,
            norm_defect_available = norm_status.available,
            norm_defect = norm_status.defect,
            norm_diagnostic_reason = norm_status.reason,
            wall_seconds = (time_ns() - layer_start_ns) / 1.0e9,
            peak_rss_bytes = Sys.maxrss(),
        )
        push!(layer_records, record)
        !isnothing(layer_callback) && layer_callback(record)
        if progress
            println(
                "layer=$(layer_index)/$(length(layers)) gates=$(length(layer)) " *
                "bond=$(record.max_bond_dimension) trunc=$(record.max_truncation_error) " *
                "bp_residual=$(record.bp_residual) norm_defect=$(record.norm_defect) " *
                "wall_s=$(round(record.wall_seconds; digits = 3))",
            )
            flush(stdout)
        end
    end

    operator = repeat("Z", length(observable_labels))
    raw_expectation_complex = expect(cache, (operator, collect(observable_labels)))
    abs(imag(raw_expectation_complex)) <= 100 * eps(real(dtype)) || throw(
        ErrorException(
            "final observable has a non-negligible imaginary part: $raw_expectation_complex",
        ),
    )
    raw_expectation = real(raw_expectation_complex)
    initial_parity = observable_parity(bits_by_label, observable_labels)
    sample_value = initial_parity * raw_expectation

    return (
        seed_id = Int(seed_id),
        seed_namespace = String(seed_namespace),
        initial_bits = bits_by_label,
        initial_parity,
        observable_labels = collect(Int, observable_labels),
        raw_expectation,
        sample_value,
        maxdim = Int(maxdim),
        cutoff = Float64(cutoff),
        dtype = string(dtype),
        bp_maxiter = Int(bp_maxiter),
        bp_tolerance = Float64(bp_tolerance),
        max_truncation_error = isempty(all_errors) ? 0.0 : maximum(all_errors),
        sum_truncation_error = sum(all_errors),
        layers = layer_records,
        wall_seconds = (time_ns() - start_ns) / 1.0e9,
        peak_rss_bytes = Sys.maxrss(),
    )
end

end
