using JSON
using Printf
using TOML

function harness_load_structured(path::AbstractString)
    ext = lowercase(splitext(path)[2])
    if ext == ".toml"
        return TOML.parsefile(path)
    end
    return open(path) do io
        JSON.parse(io)
    end
end

function harness_parse_args(args=ARGS)
    spec_path = strip(get(ENV, "HARNESS_VALIDATION_SPEC", ""))
    check_id = strip(get(ENV, "HARNESS_CHECK_ID", ""))
    output_path = strip(get(ENV, "HARNESS_CHECK_OUTPUT", ""))

    positional = String[]
    i = 1
    while i <= length(args)
        arg = args[i]
        if arg == "--check-id"
            i < length(args) || error("--check-id requires a value")
            check_id = args[i + 1]
            i += 2
        elseif arg == "--output"
            i < length(args) || error("--output requires a value")
            output_path = args[i + 1]
            i += 2
        elseif startswith(arg, "--")
            error("Unknown argument: $arg")
        else
            push!(positional, arg)
            i += 1
        end
    end

    if !isempty(positional)
        spec_path = positional[1]
        length(positional) >= 2 && (output_path = positional[2])
        length(positional) <= 2 || error("Too many positional arguments; use --check-id and --output for clarity")
    end
    isempty(spec_path) && error("Provide a validation spec path as ARGS[1] or HARNESS_VALIDATION_SPEC")

    return (
        spec_path=spec_path,
        check_id=isempty(check_id) ? nothing : check_id,
        output_path=output_path,
    )
end

function harness_resolve_path(path::AbstractString, base_dir::AbstractString)
    expanded = expanduser(path)
    return isabspath(expanded) ? normpath(expanded) : normpath(joinpath(base_dir, expanded))
end

function harness_as_float(x, label::AbstractString)
    x isa Bool && error("Expected numeric value for $label, got boolean $(repr(x))")
    x isa Real && return Float64(x)
    try
        return parse(Float64, string(x))
    catch err
        error("Expected numeric value for $label, got $(repr(x)): $err")
    end
end

function harness_pointer_token(s::AbstractString)
    return replace(replace(s, "~1" => "/"), "~0" => "~")
end

function harness_descend(value, token::AbstractString, label::AbstractString)
    if value isa AbstractDict
        haskey(value, token) || error("Missing key '$token' while resolving $label")
        return value[token]
    elseif value isa AbstractVector
        idx = parse(Int, token) + 1
        1 <= idx <= length(value) || error("Index $token outside vector while resolving $label")
        return value[idx]
    end
    error("Cannot descend through $(typeof(value)) with token '$token' while resolving $label")
end

function harness_json_pointer(value, pointer::AbstractString, label::AbstractString)
    pointer == "" && return value
    startswith(pointer, "/") || error("JSON pointer for $label must start with '/': $pointer")
    out = value
    for raw in split(pointer[2:end], "/"; keepempty=true)
        out = harness_descend(out, harness_pointer_token(raw), label)
    end
    return out
end

function harness_field_path(value, field::AbstractString, label::AbstractString)
    isempty(field) && return value
    out = value
    for token in split(field, ".")
        out = harness_descend(out, token, label)
    end
    return out
end

function harness_selector_value(selector::AbstractDict, base_dir::AbstractString, cache::AbstractDict, label::AbstractString)
    if haskey(selector, "value")
        return selector["value"]
    end
    haskey(selector, "path") || error("Selector for $label must provide either 'value' or 'path'")
    path = harness_resolve_path(string(selector["path"]), base_dir)
    record = get!(cache, path) do
        harness_load_structured(path)
    end
    if haskey(selector, "pointer")
        return harness_json_pointer(record, string(selector["pointer"]), label)
    end
    haskey(selector, "field") || error("Selector for $label with path='$path' must provide 'field' or 'pointer'")
    return harness_field_path(record, string(selector["field"]), label)
end

function harness_optional_uncertainty(check::AbstractDict, base_dir::AbstractString, cache::AbstractDict)
    parts = Float64[]
    if haskey(check, "uncertainty")
        push!(parts, harness_as_float(harness_selector_value(check["uncertainty"], base_dir, cache, "uncertainty"), "uncertainty"))
    end
    if haskey(check, "actual_uncertainty")
        push!(parts, harness_as_float(harness_selector_value(check["actual_uncertainty"], base_dir, cache, "actual_uncertainty"), "actual_uncertainty"))
    end
    if haskey(check, "reference_uncertainty")
        push!(parts, harness_as_float(harness_selector_value(check["reference_uncertainty"], base_dir, cache, "reference_uncertainty"), "reference_uncertainty"))
    end
    isempty(parts) && return nothing
    any(x -> !isfinite(x) || x < 0, parts) && error("Uncertainties must be finite non-negative numbers")
    return sqrt(sum(abs2, parts))
end

function harness_numeric_check(check::AbstractDict, base_dir::AbstractString, cache::AbstractDict)
    haskey(check, "actual") || error("Numeric check missing 'actual'")
    haskey(check, "reference") || error("Numeric check missing 'reference'")
    haskey(check, "tolerance") || error("Numeric check missing 'tolerance'")

    name = string(get(check, "name", get(check, "id", "numeric_compare")))
    actual = harness_as_float(harness_selector_value(check["actual"], base_dir, cache, "$name.actual"), "$name.actual")
    reference = harness_as_float(harness_selector_value(check["reference"], base_dir, cache, "$name.reference"), "$name.reference")
    isfinite(actual) || error("Actual value for '$name' is not finite")
    isfinite(reference) || error("Reference value for '$name' is not finite")

    uncertainty = harness_optional_uncertainty(check, base_dir, cache)
    diff = actual - reference
    metrics = Dict{String,Any}("abs" => abs(diff), "diff" => diff)
    reference != 0 && (metrics["relative"] = abs(diff) / abs(reference))
    if uncertainty !== nothing
        metrics["uncertainty"] = uncertainty
        metrics["sigma"] = uncertainty > 0 ? abs(diff) / uncertainty : (abs(diff) == 0 ? 0.0 : Inf)
    end

    tolerance = check["tolerance"]
    tolerance isa AbstractDict || error("Tolerance for '$name' must be an object")
    mode = lowercase(string(get(tolerance, "mode", "all")))
    mode in ("all", "any") || error("Tolerance mode for '$name' must be 'all' or 'any'")

    criterion_keys = [key for key in ("abs", "relative", "sigma") if haskey(tolerance, key)]
    isempty(criterion_keys) && error("Tolerance for '$name' must declare at least one of: abs, relative, sigma")

    criteria = Dict{String,Any}()
    criterion_passes = Bool[]
    for key in criterion_keys
        haskey(metrics, key) || error("Tolerance '$key' requested for '$name' but metric is unavailable")
        max_value = harness_as_float(tolerance[key], "$name.tolerance.$key")
        isfinite(max_value) && max_value >= 0 || error("Tolerance '$key' for '$name' must be finite and non-negative")
        passed = metrics[key] <= max_value
        criteria[key] = Dict("value" => metrics[key], "max" => max_value, "status" => passed ? "pass" : "fail")
        push!(criterion_passes, passed)
    end
    passed = mode == "all" ? all(criterion_passes) : any(criterion_passes)

    return Dict{String,Any}(
        "name" => name,
        "status" => passed ? "pass" : "fail",
        "actual" => actual,
        "reference" => reference,
        "metrics" => metrics,
        "criteria" => criteria,
        "mode" => mode,
    )
end

function harness_numeric_entries(spec::AbstractDict, check_id)
    checks = get(spec, "checks", nothing)
    if checks === nothing
        if haskey(spec, "actual") && haskey(spec, "reference") && haskey(spec, "tolerance")
            if check_id !== nothing
                current_id = string(get(spec, "id", get(spec, "name", "")))
                (isempty(current_id) || current_id == check_id) ||
                    error("Single numeric check id/name '$current_id' does not match requested check_id='$check_id'")
            end
            return Any[spec]
        end
        error("Validation spec must contain a 'checks' list or a single numeric check object")
    end
    checks isa AbstractVector || error("Validation spec must contain a 'checks' list")
    isempty(checks) && error("Validation spec checks list is empty")

    entries = Any[]
    for check in checks
        check isa AbstractDict || error("Every check must be an object")
        if haskey(check, "kind")
            string(check["kind"]) == "numeric_compare" || continue
            current_id = string(get(check, "id", ""))
            check_id === nothing || current_id == check_id || continue
            if haskey(check, "compare")
                compare = check["compare"]
                compare isa AbstractVector || error("numeric_compare check '$current_id' field 'compare' must be a list")
                for (idx, item) in enumerate(compare)
                    item isa AbstractDict || error("numeric_compare check '$current_id' compare item $idx must be an object")
                    entry = Dict{String,Any}(string(k) => v for (k, v) in item)
                    haskey(entry, "name") || (entry["name"] = isempty(current_id) ? "numeric_compare[$idx]" : "$current_id[$idx]")
                    entry["protocol_check_id"] = current_id
                    push!(entries, entry)
                end
            else
                push!(entries, check)
            end
        else
            if check_id !== nothing
                current_id = string(get(check, "id", get(check, "name", "")))
                current_id == check_id || continue
            end
            push!(entries, check)
        end
    end
    isempty(entries) && error(check_id === nothing ?
                             "No numeric checks found" :
                             "No numeric_compare check with id='$check_id' found")
    return entries
end

function harness_validate_numeric(spec_path::AbstractString; check_id=nothing)
    spec_abs = normpath(abspath(spec_path))
    base_dir = dirname(spec_abs)
    spec = harness_load_structured(spec_abs)
    spec isa AbstractDict || error("Validation spec must be a JSON/TOML object: $spec_abs")

    checks = harness_numeric_entries(spec, check_id)
    cache = Dict{String,Any}()
    reports = [harness_numeric_check(check, base_dir, cache) for check in checks]
    status = all(r["status"] == "pass" for r in reports) ? "pass" : "fail"
    report_id = string(get(spec, "check_id", check_id === nothing ? basename(spec_abs) : check_id))
    return Dict{String,Any}(
        "check_id" => report_id,
        "spec_path" => spec_abs,
        "status" => status,
        "checks" => reports,
    )
end

function harness_print_numeric_report(report::AbstractDict)
    @printf("Harness numeric validation: %s\n", report["check_id"])
    for check in report["checks"]
        metrics = check["metrics"]
        @printf("  [%s] %s: actual=%+.10g reference=%+.10g abs=%.6g",
                uppercase(check["status"]), check["name"], check["actual"], check["reference"], metrics["abs"])
        haskey(metrics, "sigma") && @printf(" sigma=%.6g", metrics["sigma"])
        haskey(metrics, "relative") && @printf(" relative=%.6g", metrics["relative"])
        println()
    end
    println("  verdict = $(uppercase(report["status"]))")
end

function main(args=ARGS)
    parsed = harness_parse_args(args)
    report = harness_validate_numeric(parsed.spec_path; check_id=parsed.check_id)
    if !isempty(parsed.output_path)
        open(parsed.output_path, "w") do io
            JSON.print(io, report, 2)
        end
    end
    harness_print_numeric_report(report)
    report["status"] == "pass" || exit(1)
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
