function error_metrics(values::AbstractVector, reference)
    errors = values .- reference.values
    return (; values, reference, max_error=maximum(abs.(errors)),
            rmse=sqrt(sum(abs2, errors) / length(errors)))
end

"""Read only exact metrics from the legacy strict Fig. 2 JSON schema.

Partial Redfield refreshes must fail closed if either exact panel is absent,
so they cannot silently discard a completed expensive validation.
"""
function parse_exact_baseline(json::AbstractString)
    records = Dict{Float64, NamedTuple{(:max_error, :rmse, :samples), Tuple{Float64, Float64, Int}}}()
    pattern = r"\"([0-9]+(?:\.[0-9]+)?)\":\{\"max_error\":([^,}]+),\"rmse\":([^,}]+),\"samples\":([0-9]+)"
    for found in eachmatch(pattern, json)
        ωd = parse(Float64, found.captures[1])
        records[ωd] = (; max_error=parse(Float64, found.captures[2]),
                        rmse=parse(Float64, found.captures[3]),
                        samples=parse(Int, found.captures[4]))
    end
    isempty(records) && throw(ArgumentError("baseline JSON has no exact validation records"))
    return records
end

function render_error_panel(records)
    entries = String[]
    for ωd in sort(collect(keys(records)))
        r = records[ωd]
        push!(entries, "\"$(ωd)\":{\"max_error\":$(r.max_error),\"rmse\":$(r.rmse),\"samples\":$(r.samples)}")
    end
    return "{" * join(entries, ",") * "}"
end

"""Render a versioned JSON refresh that preserves prior exact metrics verbatim."""
function render_refreshed_errors(exact::AbstractDict, redfield::AbstractDict, config::RunConfig)
    Set(keys(exact)) == Set(keys(redfield)) ||
        throw(ArgumentError("exact and refreshed Redfield frequency sets differ"))
    provenance = "{\"implementation\":\"period-resolved-driven-redfield\",\"drive\":\"transversal-sigma_z\",\"mode\":\"$(config.mode)\",\"dt_target\":$(config.dt_target),\"steps\":$(config.steps),\"frequencies\":[" * join(sort(collect(keys(redfield))), ",") * "]}"
    return "{\"provenance\":$(provenance),\"exact\":$(render_error_panel(exact)),\"redfield\":$(render_error_panel(redfield))}"
end

"""Exact uniTEMPO transient curve, kept behind the Fig. 2 baseline interface."""
function uniformtempo_exact_curve(model::SpinBosonModel, ωd::Real, dt::Real,
                                  steps::Integer, tolerance::Real)
    if_seconds = @elapsed pt = Base.invokelatest(UniformTEMPO.uniTEMPO,
        model.coupling_operator, dt, t -> bath_correlation(model, t), tolerance)
    ρ0 = ComplexF64[1 0; 0 0]
    propagation_seconds = @elapsed states = Base.invokelatest(UniformTEMPO.evolve,
        pt, ρ0, steps; h_s=t -> system_hamiltonian(model, t, ωd))
    values = [real(tr(SIGMA_Z * ρ)) for ρ in states]
    return (; values, if_build_seconds=if_seconds, propagation_seconds,
            bond_dimension=Base.invokelatest(UniformTEMPO.bond_dim, pt))
end

"""Run strict Fig. 2 references; exact and Redfield curves can never be mixed."""
function run_fig2(config::RunConfig, reference_paths::AbstractDict; exact_solver=nothing)
    model = SpinBosonModel()
    results = Dict{Float64, NamedTuple}()
    for ωd in config.frequencies
        grid = period_grid(ωd, config.dt_target)
        times = collect(0:config.steps) .* grid.dt
        paths = reference_paths[ωd]
        if paths isa AbstractString
            reference = load_reference_curve(paths, times)
            values = zeros(length(times))
            redfield_magnus!(values, model, ωd, grid.dt)
            metrics = error_metrics(values, reference)
            results[ωd] = (; times, grid, metrics..., max_error=metrics.max_error, rmse=metrics.rmse)
            continue
        end

        redfield_reference = load_reference_curve(paths.redfield, times)
        redfield_values = zeros(length(times))
        redfield_magnus!(redfield_values, model, ωd, grid.dt)
        redfield = error_metrics(redfield_values, redfield_reference)

        exact_reference = load_reference_curve(paths.exact, times)
        solver = isnothing(exact_solver) ? uniformtempo_exact_curve : exact_solver
        exact_result = solver(model, ωd, grid.dt, config.steps, config.compression_tolerance)
        length(exact_result.values) == length(times) ||
            throw(ArgumentError("exact solver returned $(length(exact_result.values)) samples for $(length(times))-point grid"))
        exact = merge(exact_result, error_metrics(exact_result.values, exact_reference))
        results[ωd] = (; times, grid, redfield, exact, max_error=exact.max_error, rmse=exact.rmse)
    end
    return results
end
import UniformTEMPO
