using JSON

function harness_load_run_spec()
    spec_path = strip(get(ENV, "HARNESS_RUN_SPEC", ""))
    isempty(spec_path) && return nothing
    spec = open(spec_path) do io
        JSON.parse(io)
    end
    spec isa AbstractDict || error("HARNESS_RUN_SPEC must point to a JSON object: $spec_path")
    return spec, spec_path
end

function harness_select_cell(spec::AbstractDict)
    cells = get(spec, "cells", Any[])
    cells isa Vector || error("Run spec field 'cells' must be a list")
    isempty(cells) && return Dict{String,Any}("cell_id"=>"local", "params"=>Dict{String,Any}())

    wanted_id = strip(get(ENV, "HARNESS_CELL_ID", ""))
    if !isempty(wanted_id)
        for cell in cells
            cell isa AbstractDict || error("Every run-spec cell must be an object")
            string(get(cell, "cell_id", "")) == wanted_id && return cell
        end
        error("No cell_id='$wanted_id' in HARNESS_RUN_SPEC")
    end

    index_raw = strip(get(ENV, "HARNESS_CELL_INDEX", get(ENV, "SLURM_ARRAY_TASK_ID", "")))
    if isempty(index_raw)
        length(cells) == 1 || error("HARNESS_RUN_SPEC has $(length(cells)) cells; set HARNESS_CELL_ID, HARNESS_CELL_INDEX, or SLURM_ARRAY_TASK_ID")
        return only(cells)
    end

    idx = parse(Int, index_raw)
    1 <= idx <= length(cells) || error("Cell index $idx outside 1:$(length(cells))")
    cell = cells[idx]
    cell isa AbstractDict || error("Run-spec cell $idx must be an object")
    return cell
end

function harness_cell_context(; default_run_dir::AbstractString="")
    loaded = harness_load_run_spec()
    if loaded === nothing
        return Dict{String,Any}(
            "run_id" => "local",
            "run_dir" => default_run_dir,
            "cell_id" => strip(get(ENV, "HARNESS_CELL_ID", "local")),
            "params" => Dict{String,Any}(),
            "settings" => Dict{String,Any}(),
            "provenance" => Dict{String,Any}(),
            "spec_path" => nothing,
        )
    end

    spec, spec_path = loaded
    cell = harness_select_cell(spec)
    params = get(cell, "params", Dict{String,Any}())
    params isa AbstractDict || error("Run-spec cell params must be an object")

    settings = Dict{String,Any}()
    spec_settings = get(spec, "settings", Dict{String,Any}())
    cell_settings = get(cell, "settings", Dict{String,Any}())
    spec_settings isa AbstractDict || error("Run spec settings must be an object")
    cell_settings isa AbstractDict || error("Run-spec cell settings must be an object")
    merge!(settings, spec_settings)
    merge!(settings, cell_settings)

    provenance = get(spec, "provenance", Dict{String,Any}())
    provenance isa AbstractDict || error("Run spec provenance must be an object")
    run_dir = string(get(spec, "run_dir", default_run_dir))
    isempty(run_dir) && error("Run spec must provide run_dir or caller must pass default_run_dir")

    return Dict{String,Any}(
        "run_id" => string(get(spec, "run_id", "local")),
        "run_dir" => run_dir,
        "cell_id" => string(get(cell, "cell_id", get(ENV, "HARNESS_CELL_INDEX", "local"))),
        "params" => params,
        "settings" => settings,
        "provenance" => provenance,
        "spec_path" => spec_path,
    )
end

function harness_get_required(d::AbstractDict, key::String)
    haskey(d, key) || error("Missing required run-spec key '$key'")
    return d[key]
end

harness_get_string(d::AbstractDict, key::String, default) = string(get(d, key, default))

function harness_get_int(d::AbstractDict, key::String, default)
    default === nothing && !haskey(d, key) && error("Missing required run-spec key '$key'")
    v = get(d, key, default)
    v isa Integer && return Int(v)
    v isa AbstractFloat && isinteger(v) && return Int(v)
    v isa AbstractFloat && error("Expected integer-valued number for key '$key', got $v")
    return parse(Int, string(v))
end

function harness_get_float(d::AbstractDict, key::String, default)
    default === nothing && !haskey(d, key) && error("Missing required run-spec key '$key'")
    v = get(d, key, default)
    v isa Real && return Float64(v)
    return parse(Float64, string(v))
end

function harness_get_bool(d::AbstractDict, key::String, default::Bool)
    v = get(d, key, default)
    v isa Bool && return v
    s = lowercase(strip(string(v)))
    s in ("true", "1", "yes") && return true
    s in ("false", "0", "no") && return false
    error("Expected boolean for key '$key', got $v")
end

function harness_json_value(x)
    x isa Symbol && return string(x)
    x isa AbstractFloat && return isfinite(x) ? x : nothing
    x isa Integer && return x
    x isa AbstractDict && return Dict{String,Any}(string(k) => harness_json_value(v) for (k, v) in x)
    x isa Tuple && return [harness_json_value(v) for v in x]
    x isa AbstractVector && return [harness_json_value(v) for v in x]
    return x
end

function harness_write_json(path::AbstractString, record; indent::Int=2)
    open(path, "w") do io
        JSON.print(io, harness_json_value(record), indent)
    end
end
