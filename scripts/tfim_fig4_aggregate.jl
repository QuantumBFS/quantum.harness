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

const DEFAULT_OUTDIR = joinpath(@__DIR__, "..", "results", "tfim_fig4_paper_grade")
const PRODUCER_SCRIPT_PATH = normpath(joinpath(@__DIR__, "tfim_fig4_paper_grade.jl"))
const PRODUCER_SCRIPT_HASH = bytes2hex(sha256(read(PRODUCER_SCRIPT_PATH)))
const DEFAULT_LS_CHAIN = [16, 32, 64, 128]
const DEFAULT_H_GRID = [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20]
const REQUIRED_MANIFEST_FIELDS = [
    "protocol_hash", "script_hash", "sources", "claims", "deviations", "artifacts",
    "status", "proposal", "proposal_kernel", "estimator", "expectation_backend", "L", "h", "L_min", "chi", "pauli_chi", "pauli_chi_check", "pauli_chi_tol", "n_steps", "pbc", "M2_anchor_at_L_min",
]
const CONSENSUS_FIELDS = [
    "protocol_hash", "script_hash", "sources", "claims", "deviations",
    "proposal", "proposal_kernel", "estimator", "L_min", "chi", "pauli_chi", "pauli_chi_check", "pauli_chi_tol", "n_steps", "pbc",
]

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

function require_manifest_provenance(d::AbstractDict, f::String)
    for field in REQUIRED_MANIFEST_FIELDS
        haskey(d, field) || error("Manifest missing required field '$field': $f")
    end
    !isempty(strip(string(d["protocol_hash"]))) || error("Manifest has empty protocol_hash: $f")
    !isempty(strip(string(d["script_hash"]))) || error("Manifest has empty script_hash: $f")
    d["script_hash"] == PRODUCER_SCRIPT_HASH ||
        error("Manifest script_hash does not match current producer script: $f")
    d["sources"] isa Vector && !isempty(d["sources"]) || error("Manifest has empty sources: $f")
    d["claims"] isa Vector && !isempty(d["claims"]) || error("Manifest has empty claims: $f")
    d["deviations"] isa Vector || error("Manifest deviations must be a list: $f")
    d["artifacts"] isa AbstractDict || error("Manifest artifacts must be a table: $f")
    haskey(d["artifacts"], "manifest") || error("Manifest artifacts missing manifest path: $f")
    d["status"] == "success" || error("Manifest is not success-tagged: $f")
    backend = string(d["expectation_backend"])
    (startswith(backend, "mps_cached_") || backend == "pauli_mps_compressed_norm") ||
        error("Manifest does not use an accepted MPS expectation backend: $f")
    d["cL"] isa Real || error("Manifest cL is not numeric: $f")
    d["se"] isa Real || error("Manifest se is not numeric: $f")
    if backend == "pauli_mps_compressed_norm"
        d["pauli_chi_error"] isa Real || error("Manifest missing numeric pauli_chi_error: $f")
        d["pauli_chi_error"] <= d["pauli_chi_tol"] ||
            error("Manifest Pauli-MPS compression gate failed: $f")
        d["se"] >= d["pauli_chi_error"] ||
            error("Manifest se does not cover Pauli-MPS compression error: $f")
    end
end

function aggregate_run_context()
    loaded = harness_load_run_spec()
    if loaded === nothing
        return (
            outdir=DEFAULT_OUTDIR,
            cell_dir=joinpath(DEFAULT_OUTDIR, "cells"),
            expected_keys=nothing,
            spec_path=nothing,
        )
    end

    spec, spec_path = loaded
    outdir = string(get(spec, "run_dir", DEFAULT_OUTDIR))
    spec_cells = get(spec, "cells", Any[])
    spec_cells isa Vector || error("Run spec field 'cells' must be a list")
    expected = Set{Tuple{Int,Float64}}()
    for cell in spec_cells
        cell isa AbstractDict || error("Every run-spec cell must be an object")
        params = get(cell, "params", nothing)
        params isa AbstractDict || error("Every run-spec cell must carry a params object for this aggregator")
        push!(expected, (harness_get_int(params, "L", nothing),
                        harness_get_float(params, "h", nothing)))
    end
    return (
        outdir=outdir,
        cell_dir=joinpath(outdir, "cells"),
        expected_keys=expected,
        spec_path=spec_path,
    )
end

function load_cells(cell_dir::AbstractString)
    isdir(cell_dir) || error("No manifest directory $cell_dir — run the per-cell job first.")
    cells = Dict{Tuple{Int,Float64}, Any}()
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
        require_manifest_provenance(d, f)
        d["L"] > d["L_min"] || error("Stale c_L manifest at or below L_min in $f")
        L = Int(d["L"])
        h = Float64(d["h"])
        haskey(cells, (L, h)) && error("Duplicate manifest for L=$L h=$h")
        cells[(L, h)] = d
    end
    return cells
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

function validate_manifest_consensus!(cells)
    first_cell = first(values(cells))
    for field in CONSENSUS_FIELDS
        expected = first_cell[field]
        for ((L, h), d) in cells
            d[field] == expected || error("Manifest consensus failure for '$field' at L=$L h=$h: $(d[field]) != $expected")
        end
    end
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
    cells = load_cells(ctx.cell_dir)
    if isempty(cells)
        error("No manifests under $(ctx.cell_dir) — run the per-cell SLURM job first.")
    end

    if ctx.expected_keys === nothing
        Ls_chain = parse_int_list_env("FIG4_EXPECTED_LS", DEFAULT_LS_CHAIN)
        h_grid   = parse_float_list_env("FIG4_EXPECTED_H_GRID", DEFAULT_H_GRID)
        validate_declared_grid!(cells, Ls_chain, h_grid)
    else
        validate_expected_keys!(cells, ctx.expected_keys)
        Ls_chain = sort(unique([L for (L, _) in ctx.expected_keys]))
        h_grid = sort(unique([h for (_, h) in ctx.expected_keys]))
    end
    validate_manifest_consensus!(cells)

    L_min    = first(values(cells))["L_min"]
    chi      = first(values(cells))["chi"]
    pauli_chi = first(values(cells))["pauli_chi"]
    pauli_chi_check = first(values(cells))["pauli_chi_check"]
    pauli_chi_tol = first(values(cells))["pauli_chi_tol"]
    n_steps  = first(values(cells))["n_steps"]
    pbc      = first(values(cells))["pbc"]
    proposal = first(values(cells))["proposal"]
    proposal_kernel = first(values(cells))["proposal_kernel"]
    estimator = first(values(cells))["estimator"]
    backends = sort(unique([string(d["expectation_backend"]) for d in values(cells)]))
    Ls_full  = [L_min; Ls_chain...]
    estimator_label = estimator == "pauli_mps_norm" ?
        "compressed Pauli-MPS normalizer contraction" : "cached Eq.-(24) ratio-chain diagnostic"

    @printf("Aggregator: L_chain=%s   h_grid=%s   L_min=%d   χ=%d   χ_P=%d→%d   N_S=%d   PBC=%s   proposal=%s/%s   estimator=%s   backends=%s\n",
            string(Ls_chain), string(h_grid), L_min, chi, pauli_chi, pauli_chi_check, n_steps, string(pbc),
            proposal_kernel, proposal, estimator, string(backends))
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
        "chi"       => chi,
        "pauli_chi" => pauli_chi,
        "pauli_chi_check" => pauli_chi_check,
        "pauli_chi_tol" => pauli_chi_tol,
        "n_steps"   => n_steps,
        "pbc"       => pbc,
        "proposal"  => proposal,
        "proposal_kernel" => proposal_kernel,
        "estimator" => estimator,
        "expectation_backends" => backends,
        "protocol_hash" => first(values(cells))["protocol_hash"],
        "script_hash" => first(values(cells))["script_hash"],
        "run_spec" => ctx.spec_path,
        "sources" => first(values(cells))["sources"],
        "claims" => first(values(cells))["claims"],
        "deviations" => first(values(cells))["deviations"],
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
