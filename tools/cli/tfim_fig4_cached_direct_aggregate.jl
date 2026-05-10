using JSON
using Plots
using Printf
using SHA

include(joinpath(@__DIR__, "harness_cell_config.jl"))

const PRODUCER_SCRIPT_PATH = normpath(joinpath(@__DIR__, "tfim_fig4_cached_direct.jl"))
const PRODUCER_SCRIPT_HASH = bytes2hex(sha256(read(PRODUCER_SCRIPT_PATH)))

function load_direct_run_spec()
    loaded = harness_load_run_spec()
    loaded === nothing && error("Set HARNESS_RUN_SPEC to aggregate cached-direct array cells.")
    spec, spec_path = loaded
    run_dir = string(get(spec, "run_dir", ""))
    isempty(run_dir) && error("Run spec must define run_dir")
    cells = get(spec, "cells", Any[])
    cells isa Vector || error("Run spec field 'cells' must be a list")
    return spec, spec_path, run_dir, cells
end

function require_direct_manifest(d::AbstractDict, path::String, params::AbstractDict)
    for field in ("status", "protocol_hash", "script_hash", "sources", "claims",
                  "deviations", "artifacts", "L", "h", "M2", "se_M2",
                  "mean_v2", "accept", "chi", "n_steps", "pbc", "proposal")
        haskey(d, field) || error("Manifest missing required field '$field': $path")
    end
    d["status"] == "success" || error("Manifest is not success-tagged: $path")
    d["script_hash"] == PRODUCER_SCRIPT_HASH ||
        error("Manifest script_hash does not match current direct producer: $path")
    d["artifacts"] isa AbstractDict || error("Manifest artifacts must be a table: $path")
    get(d["artifacts"], "manifest", nothing) == path ||
        error("Manifest artifact path mismatch: $path")
    d["L"] == harness_get_int(params, "L", nothing) ||
        error("Manifest L does not match run spec: $path")
    Float64(d["h"]) == harness_get_float(params, "h", nothing) ||
        error("Manifest h does not match run spec: $path")
    for field in ("M2", "se_M2", "mean_v2", "accept")
        d[field] isa Real && isfinite(d[field]) ||
            error("Manifest field '$field' is not finite: $path")
    end
end

function load_direct_cells(run_dir::String, spec_cells::Vector)
    records = Dict{Tuple{Int,Float64},Any}()
    for cell in spec_cells
        cell isa AbstractDict || error("Every run-spec cell must be an object")
        cell_id = string(get(cell, "cell_id", ""))
        !isempty(cell_id) || error("Run-spec cell missing cell_id")
        params = get(cell, "params", nothing)
        params isa AbstractDict || error("Run-spec cell $cell_id missing params")
        manifest = joinpath(run_dir, "cells", cell_id, "manifest.json")
        isfile(manifest) || error("Missing required direct manifest: $manifest")
        d = JSON.parsefile(manifest)
        require_direct_manifest(d, manifest, params)
        key = (Int(d["L"]), Float64(d["h"]))
        haskey(records, key) && error("Duplicate direct manifest for $key")
        records[key] = d
    end
    return records
end

function validate_direct_consensus!(records)
    first_record = first(values(records))
    for field in ("protocol_hash", "script_hash", "sources", "claims",
                  "deviations", "chi", "n_steps", "pbc", "proposal")
        expected = first_record[field]
        for ((L, h), d) in records
            d[field] == expected ||
                error("Manifest consensus failure for '$field' at L=$L h=$h: $(d[field]) != $expected")
        end
    end
end

function main()
    spec, spec_path, run_dir, spec_cells = load_direct_run_spec()
    isdir(run_dir) || mkpath(run_dir)
    records = load_direct_cells(run_dir, spec_cells)
    isempty(records) && error("Run spec has no cells")
    validate_direct_consensus!(records)

    Ls = sort(unique([L for (L, _) in keys(records)]))
    h_grid = sort(unique([h for (_, h) in keys(records)]))
    expected = Set((L, h) for L in Ls for h in h_grid)
    actual = Set(keys(records))
    missing = sort(collect(setdiff(expected, actual)))
    isempty(missing) || error("Direct run is not a rectangular L × h grid; missing $(missing)")

    M2 = Dict{Tuple{Int,Float64},Float64}()
    M2_err = Dict{Tuple{Int,Float64},Float64}()
    for ((L, h), d) in records
        M2[(L, h)] = Float64(d["M2"])
        M2_err[(L, h)] = Float64(d["se_M2"])
    end

    cL = Dict{Tuple{Int,Float64},Float64}()
    cL_err = Dict{Tuple{Int,Float64},Float64}()
    for L in Ls
        L == first(Ls) && continue
        (L ÷ 2) in Ls || error("Cannot assemble c_L for L=$L: missing L/2=$(L ÷ 2)")
        for h in h_grid
            cL[(L, h)] = 2 * M2[(L ÷ 2, h)] - M2[(L, h)]
            cL_err[(L, h)] = sqrt((2 * M2_err[(L ÷ 2, h)])^2 + M2_err[(L, h)]^2)
        end
    end

    combined = Dict(
        "model" => "1D TFIM",
        "method" => "cached direct M2 with c_L reconstructed as 2M2(L/2)-M2(L)",
        "run_spec" => spec_path,
        "Ls" => Ls,
        "h_grid" => h_grid,
        "chi" => first(values(records))["chi"],
        "n_steps" => first(values(records))["n_steps"],
        "proposal" => first(values(records))["proposal"],
        "pbc" => first(values(records))["pbc"],
        "protocol_hash" => first(values(records))["protocol_hash"],
        "script_hash" => first(values(records))["script_hash"],
        "sources" => first(values(records))["sources"],
        "claims" => first(values(records))["claims"],
        "deviations" => first(values(records))["deviations"],
        "cells" => collect(values(records)),
        "M_2" => Dict(string(L) => [M2[(L, h)] for h in h_grid] for L in Ls),
        "M_2_err" => Dict(string(L) => [M2_err[(L, h)] for h in h_grid] for L in Ls),
        "M_2_ci95" => Dict(string(L) => [1.96 * M2_err[(L, h)] for h in h_grid] for L in Ls),
        "c_L" => Dict(string(L) => [cL[(L, h)] for h in h_grid] for L in Ls[2:end]),
        "c_L_err" => Dict(string(L) => [cL_err[(L, h)] for h in h_grid] for L in Ls[2:end]),
        "c_L_ci95" => Dict(string(L) => [1.96 * cL_err[(L, h)] for h in h_grid] for L in Ls[2:end]),
    )
    harness_write_json(joinpath(run_dir, "data.json"), combined)

    palette = [:seagreen, :steelblue, :deeppink, :orange, :gray30, :purple]
    pa = plot(xlabel="h", ylabel="c_L",
              title="Fig 4(a) cached MPS direct-M2 reconstruction",
              legend=:topright)
    for (k, L) in enumerate(Ls[2:end])
        plot!(pa, h_grid, [cL[(L, h)] for h in h_grid];
              yerror=[1.96 * cL_err[(L, h)] for h in h_grid],
              marker=:circle, label="L=$L", c=palette[k])
    end
    savefig(pa, joinpath(run_dir, "panel_a_cL_vs_h.png"))

    pb = plot(xlabel="h", ylabel="m_2", title="Fig 4(b) cached MPS direct M2",
              legend=:topleft)
    for (k, L) in enumerate(Ls)
        plot!(pb, h_grid, [M2[(L, h)] / L for h in h_grid];
              yerror=[1.96 * M2_err[(L, h)] / L for h in h_grid],
              marker=:circle, label="L=$L", c=palette[k])
    end
    savefig(pb, joinpath(run_dir, "panel_b_m2_vs_h.png"))
    savefig(plot(pa, pb; layout=(1, 2), size=(1200, 450)),
            joinpath(run_dir, "fig4_combined.png"))
    println("Saved direct aggregation -> $(joinpath(run_dir, "fig4_combined.png"))")
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
