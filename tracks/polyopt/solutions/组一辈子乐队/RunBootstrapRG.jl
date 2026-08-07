include("KullCGRDM.jl")
include("VUMPSProducer.jl")
include("MPSKitAdapter.jl")

using .KullCGRDM
using .VUMPSProducer
using .MPSKitAdapter
using Dates
using JSON
using LinearAlgebra
using MosekTools
using Plots
using SHA

const FORMAL_DEPTHS = [3, 4, 6, 8, 10]
const DEFAULT_SOLVER_SETTINGS = Dict{String,Any}("MSK_IPAR_LOG" => 0)

function inventory_dict(inventory::KullResourceInventory)
    Dict{String,Any}(
        "psd_block_dimensions" => inventory.psd_block_dimensions,
        "psd_block_count" => inventory.psd_block_count,
        "real_scalar_variables" => inventory.real_scalar_variables,
        "linear_equalities" => inventory.linear_equalities,
        "coefficient_storage_bytes" => inventory.coefficient_storage_bytes,
        "peak_memory_bytes" => inventory.peak_memory_bytes,
        "estimated_wall_seconds" => inventory.estimated_wall_seconds,
        "local_feasible" => inventory.local_feasible)
end

function solver_result_dict(result::KullSolverResult)
    Dict{String,Any}(
        "lower_bound_candidate" => result.lower_bound_candidate,
        "termination_status" => string(result.termination_status),
        "primal_status" => string(result.primal_status),
        "dual_status" => string(result.dual_status),
        "relative_gap" => result.relative_gap,
        "constraint_residual" => result.constraint_residual,
        "minimum_psd_eigenvalue" => result.minimum_psd_eigenvalue,
        "runtime_seconds" => result.runtime_seconds,
        "map_fingerprint" => result.map_fingerprint,
        "vumps_upper_endpoint" => result.vumps_upper_endpoint,
        "clean" => result.clean,
        "classification" => result.classification)
end

function validate_point_record(point::AbstractDict; exact_energy::Real=EXACT_ENERGY,
        monotonic_predecessor=nothing, tolerance::Real=1e-7)
    raw = point["solver"]["lower_bound_candidate"]
    corrected = point["dual"]["corrected_lower_bound"]
    upper = point["solver"]["vumps_upper_endpoint"]
    fingerprint_ok = point["solver"]["map_fingerprint"] == point["dual"]["map_fingerprint"]
    checks = Dict{String,Bool}(
        "solver_clean" => point["solver"]["clean"] === true,
        "corrected_le_raw" => corrected <= raw + tolerance,
        "raw_le_exact" => raw <= exact_energy + tolerance,
        "exact_le_vumps" => exact_energy <= upper + tolerance,
        "same_map_fingerprint" => fingerprint_ok,
        "depth_monotonic" => isnothing(monotonic_predecessor) || raw >= monotonic_predecessor - tolerance,
        "floating_not_interval_certified" => point["dual"]["coefficient_policy"]["complete_interval_enclosure"] === false &&
            point["certification_classification"] != "interval-certified")
    checks, all(values(checks))
end

function validate_run_records(points::AbstractVector; exact_energy::Real=EXACT_ENERGY,
        tolerance::Real=1e-7)
    isempty(points) && return Dict("all_accepted" => false, "fixed_fingerprint" => false,
        "depths_strictly_increasing" => false)
    fingerprints = [point["solver"]["map_fingerprint"] for point in points]
    depths = [point["depth"] for point in points]
    Dict{String,Bool}(
        "all_accepted" => all(point["accepted"] === true for point in points),
        "fixed_fingerprint" => length(unique(fingerprints)) == 1,
        "depths_strictly_increasing" => issorted(depths) && length(unique(depths)) == length(depths),
        "all_raw_bounds_below_exact" => all(point["solver"]["lower_bound_candidate"] <= exact_energy + tolerance for point in points),
        "all_corrected_below_raw" => all(point["dual"]["corrected_lower_bound"] <=
            point["solver"]["lower_bound_candidate"] + tolerance for point in points))
end

function write_json_incrementally(path::AbstractString, payload)
    temporary = path * ".tmp"
    open(temporary, "w") do io
        JSON.print(io, payload, 2)
        write(io, '\n')
        flush(io)
    end
    mv(temporary, path; force=true)
end

function source_provenance(solution_directory::AbstractString)
    files = ["KullCGRDM.jl", "VUMPSProducer.jl", "MPSKitAdapter.jl", "RunBootstrapRG.jl"]
    Dict{String,Any}(
        "git_commit" => try readchomp(`git rev-parse HEAD`) catch; nothing end,
        "source_sha256" => Dict(file => bytes2hex(sha256(read(joinpath(solution_directory, file)))) for file in files),
        "matlab_oracle_commit" => "2e9015fff5d9bc5b170cdc6cee98fbbb928decda",
        "paper" => "Kull et al., Phys. Rev. X 14, 021008 (2024), arXiv:2212.03014")
end

function bond_product_frozen_mps(state::AbstractVector, D::Int)
    D > 0 || throw(ArgumentError("bond dimension must be positive"))
    norm(state) > 0 || throw(ArgumentError("product state must be nonzero"))
    ψ = ComplexF64.(state ./ norm(state))
    A = zeros(ComplexF64, D, length(ψ), D)
    identity = Matrix{ComplexF64}(I, D, D)
    for s in eachindex(ψ)
        A[:, s, :] = ψ[s] .* identity
    end
    FrozenUniformMPS([A]; canonical_gauge=:left,
        left_fixed_points=[Matrix{ComplexF64}(I, D, D)],
        canonical_residual=norm(sum((@view A[:, s, :])' * (@view A[:, s, :]) for s in eachindex(ψ)) - I),
        normalization_residual=abs(sum(abs2, ψ) - 1),
        vumps_settings=Dict("source" => "bond_embedded_product", "D" => D))
end

function compare_map_quality(frozen::FrozenUniformMPS, upper::Real;
        depth::Int=6, D::Int=2, k0::Int=3, clean_tolerance::Real=1e-7)
    maps = [
        ("product", bond_product_frozen_mps(ComplexF64[1, 0], D)),
        ("random_canonical", random_canonical_frozen_mps(2, D; seed=5061)),
        ("vumps", frozen)]
    comparisons = Any[]
    for (index, (label, candidate)) in pairs(maps)
        problem = build_kull_primal(HEISENBERG_H; frozen=candidate, depth, k0,
            optimizer=MosekTools.Optimizer, solver_settings=DEFAULT_SOLVER_SETTINGS,
            vumps_upper_endpoint=upper)
        problem.inventory.local_feasible || error("map-quality comparison exceeds local budget")
        println("[map quality $index/$(length(maps))] map=$label D=$D n=$depth")
        flush(stdout)
        result = solve_kull_primal!(problem; clean_tolerance,
            require_local_feasible=true, print_inventory=false)
        result.clean || error("map-quality comparison failed clean solve for $label")
        push!(comparisons, Dict{String,Any}(
            "map" => label,
            "D" => D,
            "depth" => depth,
            "k0" => k0,
            "map_fingerprint" => candidate.fingerprint,
            "lower_bound_candidate" => result.lower_bound_candidate,
            "gap_to_exact" => EXACT_ENERGY - result.lower_bound_candidate,
            "runtime_seconds" => result.runtime_seconds,
            "clean" => result.clean))
    end
    vumps_bound = only(item["lower_bound_candidate"] for item in comparisons if item["map"] == "vumps")
    for item in comparisons
        item["tightness_relative_to_vumps"] = item["lower_bound_candidate"] - vumps_bound
        item["soundness_check"] = item["lower_bound_candidate"] <= EXACT_ENERGY + clean_tolerance
    end
    Dict{String,Any}(
        "interpretation" => "Map choice changes tightness only; every clean result must retain the lower-bound direction.",
        "same_solver_budget" => true,
        "all_sound" => all(item["soundness_check"] for item in comparisons),
        "comparisons" => comparisons)
end

function qmbcertify_integration_assessment()
    Dict{String,Any}(
        "current_builder" => "independent-kull-primal-dual-oracle",
        "qmbcertify_runtime_dependency" => false,
        "decision" => "do-not-integrate-current-oracle",
        "reason" => "The fixed-size coarse omega blocks are independent PSD variables and are not representable as an existing GSB keyword without changing the verified hierarchy.",
        "future_interface" => "new shared-moment builder or pinned fork",
        "structured_npa_augmentation" => Dict(
            "status" => "deferred-follow-up-milestone",
            "bottom_connection" => "share moments with the bottom physical RDM",
            "coarse_blocks" => "retain independent omega variables",
            "certificate_requirement" => "extend the complete primal-dual certificate rather than claiming keyword compatibility"))
end

function plot_results(points, exact_energy, upper, output_directory)
    depths = [point["depth"] for point in points]
    raw = [point["solver"]["lower_bound_candidate"] for point in points]
    corrected = [point["dual"]["corrected_lower_bound"] for point in points]
    lower_error = exact_energy .- raw
    corrected_error = exact_energy .- corrected
    upper_error = fill(upper - exact_energy, length(depths))
    bracket_width = upper .- raw
    corrected_width = upper .- corrected
    variables = [point["inventory"]["real_scalar_variables"] for point in points]
    max_blocks = [maximum(point["inventory"]["psd_block_dimensions"]) for point in points]

    p1 = plot(depths, lower_error; marker=:circle, label="raw numerical optimum",
        xlabel="effective hierarchy depth n", ylabel="e₀ − lower endpoint", yscale=:log10)
    plot!(p1, depths, corrected_error; marker=:diamond, label="residual-corrected diagnostic")
    savefig(p1, joinpath(output_directory, "lower_bound_error.png"))

    p2 = plot(depths, upper_error; marker=:circle, label="VUMPS upper error",
        xlabel="effective hierarchy depth n", ylabel="energy error / bracket width", yscale=:log10)
    plot!(p2, depths, bracket_width; marker=:square, label="raw bracket width")
    plot!(p2, depths, corrected_width; marker=:diamond, label="corrected diagnostic width")
    savefig(p2, joinpath(output_directory, "upper_error_and_bracket_width.png"))

    p3 = plot(depths, variables; marker=:circle, label="real scalar variables",
        xlabel="effective hierarchy depth n", ylabel="resource count")
    plot!(p3, depths, max_blocks; marker=:square, label="largest PSD block")
    savefig(p3, joinpath(output_directory, "resource_growth.png"))
end

function run_formal_local(; output_directory::AbstractString,
        depths::Vector{Int}=copy(FORMAL_DEPTHS), D::Int=2, k0::Union{Nothing,Int}=nothing,
        vumps_maxiter::Int=300, vumps_tolerance::Float64=1e-10,
        seed::Int=1002, adapter_tolerance::Float64=1e-8,
        clean_tolerance::Float64=1e-7)
    D == 2 || throw(ArgumentError("this formal local runner is restricted to D=2"))
    selected_k0 = isnothing(k0) ? author_default_k0(2, D) : k0
    selected_k0 == 3 || throw(ArgumentError("the confirmed D=2 formal run requires author-aligned k0=3"))
    depths == FORMAL_DEPTHS || throw(ArgumentError("the confirmed formal depth grid is n={3,4,6,8,10}"))
    mkpath(output_directory)
    output_path = joinpath(output_directory, "results.json")
    solution_directory = @__DIR__
    payload = Dict{String,Any}(
        "schema_version" => 1,
        "run_status" => "initializing",
        "started_at" => string(now()),
        "setup" => Dict(
            "model" => "infinite translation-invariant spin-1/2 antiferromagnetic Heisenberg chain",
            "hamiltonian" => "Sx⊗Sx + Sy⊗Sy + Sz⊗Sz",
            "J" => 1.0, "boundary" => "infinite", "symmetry_reduction" => "none",
            "D" => D, "k0" => selected_k0, "k0_policy" => "author_default_k0",
            "depths" => depths, "solver" => "Mosek local", "slurm" => false,
            "exact_energy" => EXACT_ENERGY),
        "source_provenance" => source_provenance(solution_directory),
        "points" => Any[])
    write_json_incrementally(output_path, payload)

    println("[VUMPS] D=$D one-site start; fallback enabled")
    flush(stdout)
    produced = run_vumps_with_fallback(VUMPSSettings(; D, maxiter=vumps_maxiter,
        tol=vumps_tolerance, seed, verbosity=0, unitcell=1))
    produced.record["clean_convergence"] || error("VUMPS did not pass the clean-run gate")
    produced.record["energy_per_site"] + clean_tolerance >= EXACT_ENERGY ||
        error("VUMPS endpoint is below the exact energy")
    adapter = validate_adapter_invariants(produced.state, produced.record; atol=adapter_tolerance)
    frozen = adapter.frozen
    payload["vumps"] = produced.record
    payload["adapter"] = Dict(
        "map_fingerprint" => frozen.fingerprint,
        "transfer_eigenvalue_real" => real(adapter.transfer_eigenvalue),
        "transfer_eigenvalue_imag" => imag(adapter.transfer_eigenvalue),
        "norm_density" => adapter.norm_density,
        "dense_energy" => adapter.dense_energy,
        "transfer_error" => adapter.transfer_error,
        "norm_density_error" => adapter.norm_density_error,
        "energy_error" => adapter.energy_error,
        "canonical_residual" => frozen.canonical_residual,
        "normalization_residual" => frozen.normalization_residual)
    payload["run_status"] = "solving"
    write_json_incrementally(output_path, payload)
    println("[VUMPS] unit_cell=$(produced.record["unit_cell_length"]) E=$(produced.record["energy_per_site"]) delta=$(produced.record["algorithm_error"]) fingerprint=$(frozen.fingerprint)")
    flush(stdout)

    predecessor = nothing
    for (index, depth) in pairs(depths)
        problem = build_kull_primal(HEISENBERG_H; frozen, depth, k0=selected_k0,
            optimizer=MosekTools.Optimizer, solver_settings=DEFAULT_SOLVER_SETTINGS,
            vumps_upper_endpoint=produced.record["energy_per_site"])
        problem.inventory.local_feasible || error("depth n=$depth exceeds the declared local resource budget")
        println("[SDP $index/$(length(depths))] n=$depth blocks=$(problem.inventory.psd_block_dimensions) variables=$(problem.inventory.real_scalar_variables) peak_bytes=$(problem.inventory.peak_memory_bytes) estimated_seconds=$(problem.inventory.estimated_wall_seconds)")
        flush(stdout)
        result = solve_kull_primal!(problem; clean_tolerance, require_local_feasible=true,
            print_inventory=false)
        certificate = reconstruct_dual_certificate(problem)
        certification = certificate.coefficient_policy["complete_interval_enclosure"] === true ?
            "interval-certified" : certificate.classification
        point = Dict{String,Any}(
            "depth" => depth,
            "inventory" => inventory_dict(problem.inventory),
            "solver" => solver_result_dict(result),
            "dual" => dual_certificate_dict(certificate),
            "certification_classification" => certification)
        checks, accepted = validate_point_record(point; monotonic_predecessor=predecessor,
            tolerance=clean_tolerance)
        point["checks"] = checks
        point["accepted"] = accepted
        push!(payload["points"], point)
        write_json_incrementally(output_path, payload)
        println("[SDP $index/$(length(depths))] n=$depth raw=$(result.lower_bound_candidate) corrected=$(certificate.corrected_lower_bound) residual=$(result.constraint_residual) stationarity=$(certificate.maximum_stationarity_residual) classification=$certification accepted=$accepted")
        flush(stdout)
        accepted || error("depth n=$depth failed result validation")
        predecessor = result.lower_bound_candidate
    end

    payload["run_checks"] = validate_run_records(payload["points"])
    all(values(payload["run_checks"])) || error("complete depth curve failed validation")
    payload["map_quality"] = compare_map_quality(frozen, produced.record["energy_per_site"];
        D, k0=selected_k0, clean_tolerance)
    payload["map_quality"]["all_sound"] || error("map-quality comparison violated bound direction")
    payload["qmbcertify_integration"] = qmbcertify_integration_assessment()
    write_json_incrementally(output_path, payload)
    plot_results(payload["points"], EXACT_ENERGY, produced.record["energy_per_site"], output_directory)
    payload["artifacts"] = Dict(
        "results_json" => output_path,
        "lower_bound_error_plot" => joinpath(output_directory, "lower_bound_error.png"),
        "upper_error_bracket_plot" => joinpath(output_directory, "upper_error_and_bracket_width.png"),
        "resource_growth_plot" => joinpath(output_directory, "resource_growth.png"))
    payload["run_status"] = "verified_complete"
    payload["completed_at"] = string(now())
    write_json_incrementally(output_path, payload)
    println("[complete] verified output=$output_path")
    flush(stdout)
    payload
end

if abspath(PROGRAM_FILE) == @__FILE__
    output_directory = isempty(ARGS) ?
        normpath(joinpath(@__DIR__, "..", "..", "results", "kull-vumps-d2-local-2026-07-29")) : ARGS[1]
    run_formal_local(; output_directory=abspath(output_directory))
end
