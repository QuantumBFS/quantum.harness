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

function harness_merged_cell_settings(spec::AbstractDict, cell::AbstractDict)
    settings = Dict{String,Any}()
    spec_settings = get(spec, "settings", Dict{String,Any}())
    cell_settings = get(cell, "settings", Dict{String,Any}())
    spec_settings isa AbstractDict || error("Run spec settings must be an object")
    cell_settings isa AbstractDict || error("Run-spec cell settings must be an object")
    merge!(settings, Dict{String,Any}(string(k) => v for (k, v) in spec_settings))
    merge!(settings, Dict{String,Any}(string(k) => v for (k, v) in cell_settings))
    return settings
end

function harness_merged_cell_provenance(spec::AbstractDict, cell::AbstractDict)
    provenance = Dict{String,Any}()
    spec_provenance = get(spec, "provenance", Dict{String,Any}())
    cell_provenance = get(cell, "provenance", Dict{String,Any}())
    spec_provenance isa AbstractDict || error("Run spec provenance must be an object")
    cell_provenance isa AbstractDict || error("Run-spec cell provenance must be an object")
    merge!(provenance, Dict{String,Any}(string(k) => v for (k, v) in spec_provenance))
    merge!(provenance, Dict{String,Any}(string(k) => v for (k, v) in cell_provenance))
    return provenance
end

function harness_expected_cell_settings(spec::AbstractDict)
    cells = get(spec, "cells", Any[])
    cells isa Vector || error("Run spec field 'cells' must be a list")
    out = Dict{String,Any}()
    for cell in cells
        cell isa AbstractDict || error("Every run-spec cell must be an object")
        cell_id = string(get(cell, "cell_id", ""))
        !isempty(cell_id) || error("Every run-spec cell must carry a nonempty cell_id")
        haskey(out, cell_id) && error("Duplicate run-spec cell_id '$cell_id'")
        out[cell_id] = harness_merged_cell_settings(spec, cell)
    end
    return out
end

function harness_expected_cell_provenance(spec::AbstractDict)
    cells = get(spec, "cells", Any[])
    cells isa Vector || error("Run spec field 'cells' must be a list")
    out = Dict{String,Any}()
    for cell in cells
        cell isa AbstractDict || error("Every run-spec cell must be an object")
        cell_id = string(get(cell, "cell_id", ""))
        !isempty(cell_id) || error("Every run-spec cell must carry a nonempty cell_id")
        haskey(out, cell_id) && error("Duplicate run-spec cell_id '$cell_id'")
        out[cell_id] = harness_merged_cell_provenance(spec, cell)
    end
    return out
end

function harness_validate_manifest_settings(manifest::AbstractDict, expected::AbstractDict; path::AbstractString="manifest")
    settings = get(manifest, "settings", nothing)
    settings isa AbstractDict || error("Manifest settings must be an object: $path")
    settings_s = Dict{String,Any}(string(k) => v for (k, v) in settings)
    for (key, value) in expected
        haskey(settings_s, key) || error("Manifest settings missing declared key '$key': $path")
        settings_s[key] == value ||
            error("Manifest settings.$key=$(repr(settings_s[key])) does not match run-spec value $(repr(value)): $path")
    end
    return true
end

function harness_validate_manifest_provenance(manifest::AbstractDict, expected::AbstractDict;
                                             fields=nothing,
                                             path::AbstractString="manifest")
    field_names = fields === nothing ? sort(collect(string(k) for k in keys(expected))) : [string(x) for x in fields]
    for key in field_names
        haskey(expected, key) || error("Expected provenance missing key '$key': $path")
        haskey(manifest, key) || error("Manifest missing declared provenance key '$key': $path")
        manifest[key] == expected[key] ||
            error("Manifest provenance.$key=$(repr(manifest[key])) does not match run-spec value $(repr(expected[key])): $path")
    end
    return true
end

function harness_push_unique!(values::Vector{Any}, value)
    any(x -> x == value, values) || push!(values, value)
    return values
end

function harness_summarize_manifest_settings(manifests)
    manifests isa AbstractVector || error("Manifests must be a list")
    keys_seen = Set{String}()
    normalized = Any[]
    for manifest in manifests
        manifest isa AbstractDict || error("Every manifest must be an object")
        settings = get(manifest, "settings", nothing)
        settings isa AbstractDict || error("Every manifest must carry a settings object")
        settings_s = Dict{String,Any}(string(k) => v for (k, v) in settings)
        push!(normalized, Dict{String,Any}("manifest" => manifest, "settings" => settings_s))
        for key in keys(settings_s)
            push!(keys_seen, key)
        end
    end

    constants = Dict{String,Any}()
    varying = Dict{String,Any}()
    for key in sort(collect(keys_seen))
        values = Any[]
        for item in normalized
            settings = item["settings"]
            value = haskey(settings, key) ? settings[key] : nothing
            harness_push_unique!(values, value)
        end
        if length(values) == 1
            constants[key] = only(values)
        else
            entries = Any[]
            for item in sort(normalized; by=item -> string(get(item["manifest"], "cell_id", "")))
                manifest = item["manifest"]
                settings = item["settings"]
                push!(entries, Dict{String,Any}(
                    "cell_id" => string(get(manifest, "cell_id", "")),
                    "params" => get(manifest, "params", Dict{String,Any}()),
                    "value" => haskey(settings, key) ? settings[key] : nothing,
                ))
            end
            varying[key] = entries
        end
    end
    return Dict{String,Any}("constant" => constants, "varying" => varying)
end

function harness_summarize_manifest_fields(manifests, fields)
    manifests isa AbstractVector || error("Manifests must be a list")
    field_names = [string(field) for field in fields]
    constants = Dict{String,Any}()
    varying = Dict{String,Any}()
    for field in field_names
        values = Any[]
        for manifest in manifests
            manifest isa AbstractDict || error("Every manifest must be an object")
            value = haskey(manifest, field) ? manifest[field] : nothing
            harness_push_unique!(values, value)
        end
        if length(values) == 1
            constants[field] = only(values)
        else
            entries = Any[]
            for manifest in sort(manifests; by=item -> string(get(item, "cell_id", "")))
                push!(entries, Dict{String,Any}(
                    "cell_id" => string(get(manifest, "cell_id", "")),
                    "params" => get(manifest, "params", Dict{String,Any}()),
                    "value" => haskey(manifest, field) ? manifest[field] : nothing,
                ))
            end
            varying[field] = entries
        end
    end
    return Dict{String,Any}("constant" => constants, "varying" => varying)
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

    settings = harness_merged_cell_settings(spec, cell)

    provenance = harness_merged_cell_provenance(spec, cell)
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
