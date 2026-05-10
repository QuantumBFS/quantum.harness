# Aggregator for cached Eq.-(24) Fig 4 diagnostic runs. Collects all per-cell manifests
# (written by tfim_fig4_paper_grade.jl in per-cell SLURM mode), runs Stage 3
# (increment recursion), and emits panels (a), (b), the σ_{m_2}-vs-L inset, and
# data.json + summary.
#
# Run after the SLURM array job finishes:
#   julia --project=julia-env scripts/tfim_fig4_aggregate.jl
#
# Strict assembly: every declared cell must be present, fresh enough to carry
# provenance, and consensus-compatible before plots or data.json are written.

using JSON
using Printf
using Plots
using SHA

include(joinpath(@__DIR__, "..", "tools", "cli", "harness_cell_config.jl"))
include(joinpath(@__DIR__, "..", "tools", "cli", "harness_manifest_evidence.jl"))

const DEFAULT_OUTDIR = joinpath(@__DIR__, "..", "results", "tfim_fig4_paper_grade")
const PRODUCER_SCRIPT_PATH = normpath(joinpath(@__DIR__, "tfim_fig4_paper_grade.jl"))
const PRODUCER_SCRIPT_HASH = bytes2hex(sha256(read(PRODUCER_SCRIPT_PATH)))
const DEFAULT_LS_CHAIN = [16, 32, 64, 128]
const DEFAULT_H_GRID = [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20]
const DEFAULT_MANIFEST_CONSENSUS_FIELDS = [
    "protocol_hash", "script_hash", "sources", "claims", "deviations", "L_min",
]
const DEFAULT_MANIFEST_CONTRACT = Dict{String,Any}(
    "required_fields" => Any[
        "protocol_hash", "script_hash", "sources", "claims", "deviations", "artifacts",
        "status", "cell_id", "params", "settings", "proposal", "proposal_kernel",
        "estimator", "expectation_backend", "L", "h", "L_min", "chi",
        "n_steps", "pbc", "M2_anchor_at_L_min",
    ],
    "nonempty_fields" => Any["protocol_hash", "script_hash", "sources", "claims", "artifacts"],
    "equals" => Any[
        Dict("field"=>"status", "value"=>"success"),
        Dict("field"=>"script_hash", "value"=>PRODUCER_SCRIPT_HASH),
    ],
    "numeric_fields" => Any[
        "cL", "se", "L", "h", "L_min", "chi", "n_steps", "M2_anchor_at_L_min",
    ],
    "evidence_sets" => Any[
        Dict("evidence_field"=>"symmetry_evidence",
             "declarations_field"=>"symmetry_checks",
             "required"=>false),
    ],
)
const MANIFEST_CONTRACT_LIST_KEYS = (
    "required_fields", "nonempty_fields", "equals", "list_contains",
    "numeric_fields", "optional_numeric_fields", "numeric_bounds", "evidence_sets",
)

function parse_int_list_env(name::String, default::Vector{Int})
    raw = strip(get(ENV, name, ""))
    isempty(raw) && return default
    return [parse(Int, strip(x)) for x in split(raw, ',') if !isempty(strip(x))]
end

function parse_float_list_env(name::String, default::Vector{Float64})
    raw = strip(get(ENV, name, ""))
    isempty(raw) && return default
    return [parse(Float64, strip(x)) for x in split(raw, ',') if !isempty(strip(x))]
end

function merged_manifest_contract(extra)
    extra === nothing && return DEFAULT_MANIFEST_CONTRACT
    extra isa AbstractDict || error("Run-spec assembly.manifest_contract must be an object")
    out = Dict{String,Any}()
    for key in MANIFEST_CONTRACT_LIST_KEYS
        items = Any[]
        append!(items, get(DEFAULT_MANIFEST_CONTRACT, key, Any[]))
        append!(items, get(extra, key, Any[]))
        isempty(items) || (out[key] = items)
    end
    return out
end

function require_manifest_provenance(d::AbstractDict, f::String, contract::AbstractDict)
    harness_validate_manifest_contract(d, contract; path=f)
    d["artifacts"] isa AbstractDict || error("Manifest artifacts must be a table: $f")
    haskey(d["artifacts"], "manifest") || error("Manifest artifacts missing manifest path: $f")
end

function aggregate_run_context()
    loaded = harness_load_run_spec()
    if loaded === nothing
        return (
            outdir=DEFAULT_OUTDIR,
            cell_dir=joinpath(DEFAULT_OUTDIR, "cells"),
            expected_keys=nothing,
            expected_cell_ids=nothing,
            spec_path=nothing,
            manifest_contract=DEFAULT_MANIFEST_CONTRACT,
            consensus_fields=DEFAULT_MANIFEST_CONSENSUS_FIELDS,
            expected_settings=nothing,
            expected_provenance=nothing,
            provenance_fields=nothing,
        )
    end

    spec, spec_path = loaded
    outdir = string(get(spec, "run_dir", DEFAULT_OUTDIR))
    assembly = get(spec, "assembly", Dict{String,Any}())
    assembly isa AbstractDict || error("Run spec field 'assembly' must be an object when present")
    extra_contract = get(assembly, "manifest_contract", get(spec, "manifest_contract", nothing))
    consensus_fields = get(assembly, "consensus_fields",
                           get(spec, "manifest_consensus_fields", DEFAULT_MANIFEST_CONSENSUS_FIELDS))
    consensus_fields isa Vector || error("Run-spec consensus_fields must be a list")
    provenance_fields = get(assembly, "provenance_fields", get(spec, "manifest_provenance_fields", nothing))
    provenance_fields === nothing || provenance_fields isa Vector ||
        error("Run-spec provenance_fields must be a list")
    spec_cells = get(spec, "cells", Any[])
    spec_cells isa Vector || error("Run spec field 'cells' must be a list")
    expected = Set{Tuple{Int,Float64}}()
    expected_ids = Set{String}()
    for cell in spec_cells
        cell isa AbstractDict || error("Every run-spec cell must be an object")
        cell_id = string(get(cell, "cell_id", ""))
        !isempty(cell_id) || error("Every run-spec cell must carry a nonempty cell_id")
        cell_id in expected_ids && error("Duplicate run-spec cell_id '$cell_id'")
        push!(expected_ids, cell_id)
        params = get(cell, "params", nothing)
        params isa AbstractDict || error("Every run-spec cell must carry a params object for this aggregator")
        push!(expected, (harness_get_int(params, "L", nothing),
                        harness_get_float(params, "h", nothing)))
    end
    return (
        outdir=outdir,
        cell_dir=joinpath(outdir, "cells"),
        expected_keys=expected,
        expected_cell_ids=expected_ids,
        spec_path=spec_path,
        manifest_contract=merged_manifest_contract(extra_contract),
        consensus_fields=[string(x) for x in consensus_fields],
        expected_settings=harness_expected_cell_settings(spec),
        expected_provenance=harness_expected_cell_provenance(spec),
        provenance_fields=provenance_fields === nothing ? nothing : [string(x) for x in provenance_fields],
    )
end

function load_cells(cell_dir::AbstractString, contract::AbstractDict)
    isdir(cell_dir) || error("No manifest directory $cell_dir — run the per-cell job first.")
    cells = Dict{Tuple{Int,Float64}, Any}()
    cell_ids = Set{String}()
    manifest_paths = String[]
    for (root, _, files) in walkdir(cell_dir)
        for name in files
            if name == "manifest.json" || match(r"^manifest_L\d+_h\d+\.\d+\.json$", name) !== nothing
                push!(manifest_paths, joinpath(root, name))
            end
        end
    end
    for f in manifest_paths
        d = open(f) do io; JSON.parse(io); end
        require_manifest_provenance(d, f, contract)
        d["L"] > d["L_min"] || error("Stale c_L manifest at or below L_min in $f")
        cell_id = string(d["cell_id"])
        cell_id in cell_ids && error("Duplicate manifest for cell_id=$cell_id")
        push!(cell_ids, cell_id)
        L = Int(d["L"])
        h = Float64(d["h"])
        haskey(cells, (L, h)) && error("Duplicate manifest for L=$L h=$h")
        cells[(L, h)] = d
    end
    return cells, cell_ids
end

function validate_declared_grid!(cells, Ls_chain::Vector{Int}, h_grid::Vector{Float64})
    expected = Set((L, h) for L in Ls_chain for h in h_grid)
    actual = Set(keys(cells))
    missing = sort(collect(setdiff(expected, actual)))
    extra = sort(collect(setdiff(actual, expected)))
    isempty(missing) || error("Missing required manifests: $(missing)")
    isempty(extra) || error("Unexpected manifests outside declared grid: $(extra)")
end

function validate_expected_keys!(cells, expected_keys::Set{Tuple{Int,Float64}})
    actual = Set(keys(cells))
    missing = sort(collect(setdiff(expected_keys, actual)))
    extra = sort(collect(setdiff(actual, expected_keys)))
    isempty(missing) || error("Missing required manifests from run spec: $(missing)")
    isempty(extra) || error("Unexpected manifests outside run spec: $(extra)")
end

function validate_expected_cell_ids!(cell_ids, expected_cell_ids::Set{String})
    missing = sort(collect(setdiff(expected_cell_ids, cell_ids)))
    extra = sort(collect(setdiff(cell_ids, expected_cell_ids)))
    isempty(missing) || error("Missing required manifest cell_ids from run spec: $(missing)")
    isempty(extra) || error("Unexpected manifest cell_ids outside run spec: $(extra)")
end

function validate_manifest_consensus!(cells, consensus_fields::Vector{String})
    first_cell = first(values(cells))
    for field in consensus_fields
        expected = first_cell[field]
        for ((L, h), d) in cells
            d[field] == expected || error("Manifest consensus failure for '$field' at L=$L h=$h: $(d[field]) != $expected")
        end
    end
end

function validate_expected_settings!(cells, expected_settings)
    expected_settings === nothing && return true
    for d in values(cells)
        cell_id = string(d["cell_id"])
        haskey(expected_settings, cell_id) || error("No run-spec settings found for manifest cell_id=$cell_id")
        harness_validate_manifest_settings(d, expected_settings[cell_id]; path="cell_id=$cell_id")
    end
    return true
end

function validate_expected_provenance!(cells, expected_provenance, provenance_fields)
    expected_provenance === nothing && return true
    for d in values(cells)
        cell_id = string(d["cell_id"])
        haskey(expected_provenance, cell_id) || error("No run-spec provenance found for manifest cell_id=$cell_id")
        harness_validate_manifest_provenance(
            d, expected_provenance[cell_id]; fields=provenance_fields, path="cell_id=$cell_id")
    end
    return true
end

function sorted_cell_records(cells)
    return sort(collect(values(cells)); by=d -> (Int(d["L"]), Float64(d["h"]), string(d["cell_id"])))
end

function summary_constant(summary::AbstractDict, key::AbstractString, default=nothing)
    constants = summary["constant"]
    return haskey(constants, key) ? constants[key] : default
end

function summary_report_value(summary::AbstractDict, key::AbstractString, legacy)
    haskey(summary["constant"], key) && return summary["constant"][key]
    haskey(summary["varying"], key) && return "mixed"
    return legacy
end

function summary_keys(d::AbstractDict)
    return sort(collect(string(k) for k in keys(d)))
end

function increment_recursion_M2(M2_min::Float64, L_min::Int, cs::Vector{Float64})
    out = Dict{Int, Float64}()
    out[L_min] = M2_min
    M2_prev = M2_min
    for (k, c) in enumerate(cs)
        L_k = L_min * 2^k
        out[L_k] = 2 * M2_prev - c
        M2_prev = out[L_k]
    end
    return out
end

function main()
    ctx = aggregate_run_context()
    cells, cell_ids = load_cells(ctx.cell_dir, ctx.manifest_contract)
    if isempty(cells)
        error("No manifests under $(ctx.cell_dir) — run the per-cell SLURM job first.")
    end

    if ctx.expected_keys === nothing
        Ls_chain = parse_int_list_env("FIG4_EXPECTED_LS", DEFAULT_LS_CHAIN)
        h_grid   = parse_float_list_env("FIG4_EXPECTED_H_GRID", DEFAULT_H_GRID)
        validate_declared_grid!(cells, Ls_chain, h_grid)
    else
        validate_expected_cell_ids!(cell_ids, ctx.expected_cell_ids)
        validate_expected_keys!(cells, ctx.expected_keys)
        Ls_chain = sort(unique([L for (L, _) in ctx.expected_keys]))
        h_grid = sort(unique([h for (_, h) in ctx.expected_keys]))
    end
    validate_manifest_consensus!(cells, ctx.consensus_fields)
    validate_expected_settings!(cells, ctx.expected_settings)
    validate_expected_provenance!(cells, ctx.expected_provenance, ctx.provenance_fields)

    L_min    = first(values(cells))["L_min"]
    cell_records = sorted_cell_records(cells)
    settings_summary = harness_summarize_manifest_settings(cell_records)
    provenance_summary = harness_summarize_manifest_fields(
        cell_records, ["protocol_hash", "script_hash", "sources", "claims", "deviations"])
    proposal = summary_report_value(settings_summary, "proposal", first(values(cells))["proposal"])
    proposal_kernel = summary_report_value(settings_summary, "proposal_kernel", first(values(cells))["proposal_kernel"])
    estimator = summary_report_value(settings_summary, "estimator", first(values(cells))["estimator"])
    backends = sort(unique([string(d["expectation_backend"]) for d in values(cells)]))
    Ls_full  = [L_min; Ls_chain...]
    estimator_label = string(summary_report_value(settings_summary, "estimator_label",
                                                  get(first(values(cells)), "estimator_label",
                                                      replace(string(estimator), "_" => " "))))

    @printf("Aggregator: L_chain=%s   h_grid=%s   L_min=%d   proposal=%s/%s   estimator=%s   backends=%s\n",
            string(Ls_chain), string(h_grid), L_min, proposal_kernel, proposal, estimator, string(backends))
    @printf("Settings   : constant=%s   varying=%s\n",
            string(summary_keys(settings_summary["constant"])),
            string(summary_keys(settings_summary["varying"])))
    flush(stdout)

    # M_2 anchors at L_min (per-h, taken from any cell at that h).
    M2_anchor = Dict{Float64, Float64}()
    for h in h_grid
        anchor = cells[(first(Ls_chain), h)]["M2_anchor_at_L_min"]
        for L in Ls_chain
            cells[(L, h)]["M2_anchor_at_L_min"] == anchor ||
                error("M2 anchor consensus failure at h=$h between L=$(first(Ls_chain)) and L=$L")
        end
        M2_anchor[h] = anchor
    end

    # Stage 3: increment recursion per h.
    M2_grid = Dict{Tuple{Int,Float64}, Float64}()
    M2_err  = Dict{Tuple{Int,Float64}, Float64}()
    cL_data = Dict{Tuple{Int,Float64}, Float64}()
    cL_err  = Dict{Tuple{Int,Float64}, Float64}()
    println("\n############ Stage 3: increment recursion ############")
    for h in h_grid
        for L in Ls_chain
            cL_data[(L, h)] = cells[(L, h)]["cL"]
            cL_err[(L, h)]  = cells[(L, h)]["se"]
        end

        cs   = [cL_data[(L, h)] for L in Ls_chain]
        cerr = [cL_err[(L, h)]  for L in Ls_chain]
        rec  = increment_recursion_M2(M2_anchor[h], L_min, cs)
        M2_grid[(L_min, h)] = rec[L_min]
        M2_err[(L_min, h)]  = 0.0
        prev_err = 0.0
        for (k, L) in enumerate(Ls_chain)
            M2_grid[(L, h)] = rec[L]
            err_k = sqrt((2*prev_err)^2 + cerr[k]^2)
            M2_err[(L, h)] = err_k
            prev_err = err_k
        end
        @printf("  h=%.2f   m_2(L_min=%d) = %.5f   m_2(L=%d) = %.5f ± %.5f\n",
                h, L_min, rec[L_min]/L_min, last(Ls_chain),
                rec[last(Ls_chain)] / last(Ls_chain),
                M2_err[(last(Ls_chain), h)] / last(Ls_chain))
    end
    flush(stdout)

    # data.json: full reproduction record.
    combined = Dict(
        "model"     => "1D TFIM",
        "estimator_description" => estimator_label,
        "L_min"     => L_min,
        "Ls_chain"  => Ls_chain,
        "Ls_full"   => Ls_full,
        "h_grid"    => h_grid,
        "settings_summary" => settings_summary,
        "provenance_summary" => provenance_summary,
        "cells" => cell_records,
        "initial_state" => summary_report_value(settings_summary, "initial_state", nothing),
        "symmetry_checks" => summary_report_value(settings_summary, "symmetry_checks", nothing),
        "symmetry_evidence" => [d["symmetry_evidence"] for d in values(cells)],
        "proposal"  => proposal,
        "proposal_kernel" => proposal_kernel,
        "estimator" => estimator,
        "expectation_backends" => backends,
        "protocol_hash" => summary_report_value(provenance_summary, "protocol_hash", nothing),
        "script_hash" => summary_report_value(provenance_summary, "script_hash", nothing),
        "run_spec" => ctx.spec_path,
        "sources" => summary_report_value(provenance_summary, "sources", nothing),
        "claims" => summary_report_value(provenance_summary, "claims", nothing),
        "deviations" => summary_report_value(provenance_summary, "deviations", nothing),
        "M2_anchor" => Dict(string(h) => M2_anchor[h] for h in h_grid),
        "c_L"       => Dict(string(L) => [get(cL_data, (L, h), NaN)  for h in h_grid] for L in Ls_chain),
        "c_L_err"   => Dict(string(L) => [get(cL_err,  (L, h), NaN)  for h in h_grid] for L in Ls_chain),
        "c_L_ci95"  => Dict(string(L) => [1.96 * get(cL_err, (L, h), NaN) for h in h_grid] for L in Ls_chain),
        "M_2"       => Dict(string(L) => [get(M2_grid, (L, h), NaN)  for h in h_grid] for L in Ls_full),
        "M_2_err"   => Dict(string(L) => [get(M2_err,  (L, h), NaN)  for h in h_grid] for L in Ls_full),
        "M_2_ci95"  => Dict(string(L) => [1.96 * get(M2_err, (L, h), NaN) for h in h_grid] for L in Ls_full),
        "expected_cells" => length(Ls_chain) * length(h_grid),
    )
    harness_write_json(joinpath(ctx.outdir, "data.json"), combined)
    println("Saved → $(joinpath(ctx.outdir, "data.json"))")
    flush(stdout)

    # Plots: panel (a), panel (b), inset.
    palette = [:steelblue, :firebrick, :seagreen, :darkorange, :mediumorchid]

    pa = plot(xlabel="h", ylabel="c_L = 2 M_2(L/2) − M_2(L)",
              title="Fig 4(a) — $estimator_label",
              xticks=h_grid, legend=:bottomright)
    for (k, L) in enumerate(Ls_chain)
        cs   = [get(cL_data, (L, h), NaN) for h in h_grid]
        errs = [1.96 * get(cL_err, (L, h), NaN) for h in h_grid]
        plot!(pa, h_grid, cs; yerror=errs,
              seriestype=:scatter, marker=:circle, ms=6, c=palette[k],
              label="L=$L")
        plot!(pa, h_grid, cs; ls=:dot, c=palette[k], lw=1, label="")
    end
    savefig(pa, joinpath(ctx.outdir, "panel_a_cL_vs_h.png"))

    pb = plot(xlabel="h", ylabel="m_2 = M_2 / L",
              title="Fig 4(b) — m_2 via increment recursion (diagnostic)",
              xticks=h_grid, legend=:topright)
    for (k, L) in enumerate(Ls_full)
        m2s    = [get(M2_grid, (L, h), NaN) / L for h in h_grid]
        m2errs = [1.96 * get(M2_err, (L, h), NaN) / L for h in h_grid]
        plot!(pb, h_grid, m2s; yerror=m2errs,
              seriestype=:scatter, marker=:circle, ms=6, c=palette[k],
              label="L=$L")
        plot!(pb, h_grid, m2s; ls=:dot, c=palette[k], lw=1, label="")
    end
    savefig(pb, joinpath(ctx.outdir, "panel_b_m2_vs_h.png"))

    pc = plot(pa, pb; layout=(1,2), size=(1100, 450))
    savefig(pc, joinpath(ctx.outdir, "fig4_combined.png"))

    # Inset: σ_{m_2}(L) at h_c on log-log scale.
    h_at_critical = h_grid[argmin(abs.(h_grid .- 1.0))]
    sigmas_full = [1.96 * get(M2_err, (L, h_at_critical), NaN) / L for L in Ls_full]
    valid = .!isnan.(sigmas_full) .& (sigmas_full .> 0)
    if any(valid)
        Ls_valid = Float64.(Ls_full[valid])
        sigs     = sigmas_full[valid]
        pi_ = plot(xlabel="L", ylabel="σ(m_2) at h_c=1",
                   title="Fig 4(b) inset — reported error vs L (log-log)",
                   xscale=:log10, yscale=:log10, legend=:topright)
        plot!(pi_, Ls_valid, sigs; seriestype=:scatter, marker=:circle, ms=8, c=:firebrick,
              label=estimator_label)
        plot!(pi_, Ls_valid, sigs; ls=:solid, c=:firebrick, lw=1, label="")
        if length(Ls_valid) ≥ 2 && sigs[1] > 0
            ref_inv_sqrt = sigs[1] .* sqrt(Ls_valid[1] ./ Ls_valid)
            ref_inv_log  = sigs[1] .* (log(Ls_valid[1]) ./ log.(Ls_valid))
            plot!(pi_, Ls_valid, ref_inv_sqrt; ls=:dash, c=:gray,  lw=1, label="∝ 1/√L (ref)")
            plot!(pi_, Ls_valid, ref_inv_log;  ls=:dot,  c=:black, lw=1, label="∝ 1/log L (ref)")
        end
        savefig(pi_, joinpath(ctx.outdir, "panel_b_inset_sigma_vs_L.png"))
    end

    println("Saved plots → panel_a_cL_vs_h.png, panel_b_m2_vs_h.png, panel_b_inset_sigma_vs_L.png, fig4_combined.png")
    flush(stdout)

    # Summary.
    println("\n=========================================================")
    println("SUMMARY — Fig 4 $estimator_label")
    println("=========================================================")
    @printf("  Cells: %d / %d collected.\n",
            length(cells), length(Ls_chain)*length(h_grid))
    println("  c_L extremum (most negative) per L:")
    for L in Ls_chain
        cs = Float64[]
        hs = Float64[]
        for h in h_grid
            haskey(cL_data, (L, h)) || continue
            push!(cs, cL_data[(L, h)]); push!(hs, h)
        end
        if !isempty(cs)
            idx_min = argmin(cs)
            @printf("    L=%3d  argmin(c_L) at h=%.2f  c_L = %+.5f ± %.5f\n",
                    L, hs[idx_min], cs[idx_min],
                    get(cL_err, (L, hs[idx_min]), NaN))
        end
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
