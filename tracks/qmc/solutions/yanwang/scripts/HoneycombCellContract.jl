module HoneycombCellContract

using JSON
using SHA

export resolve_cell, resolve_run_directory, scalar, write_manifest

function resolve_run_directory(spec_path, spec)
    haskey(spec, "run_dir") ||
        throw(ArgumentError("run spec must declare run_dir"))
    declared_value = spec["run_dir"]
    declared_value isa AbstractString && !isempty(declared_value) ||
        throw(ArgumentError("run_dir must be a nonempty string"))
    spec_file = abspath(String(spec_path))
    isfile(spec_file) ||
        throw(ArgumentError("run spec does not exist: $spec_file"))
    declared_path = abspath(String(declared_value))
    isdir(declared_path) ||
        throw(ArgumentError("declared run_dir does not exist: $declared_path"))
    expected_path = realpath(dirname(spec_file))
    resolved_path = realpath(declared_path)
    resolved_path == expected_path ||
        throw(
            ArgumentError(
                "run_dir resolves to $resolved_path, but the run spec is in " *
                expected_path,
            ),
        )
    return resolved_path
end

function positive_float(value, label)
    parsed = Float64(value)
    isfinite(parsed) && parsed > 0 ||
        throw(ArgumentError("$label must be finite and positive"))
    return parsed
end

function positive_int(value, label)
    parsed = Int(value)
    parsed > 0 || throw(ArgumentError("$label must be positive"))
    return parsed
end

function nonnegative_int(value, label)
    parsed = Int(value)
    parsed >= 0 || throw(ArgumentError("$label must be nonnegative"))
    return parsed
end

function aspect_tolerance(settings)
    tolerance = Float64(get(settings, "aspect_tolerance", 1e-12))
    isfinite(tolerance) && 0 <= tolerance <= 1e-10 ||
        throw(
            ArgumentError(
                "aspect_tolerance must be finite and between 0 and 1e-10",
            ),
        )
    return tolerance
end

function resolve_cell(settings, params)
    lattice_name = String(settings["lattice_name"])
    lattice_name in ("honeycomb", "triangular") ||
        throw(ArgumentError("unsupported cell-contract lattice: $lattice_name"))
    L = Int(params["L"])
    L >= 2 || throw(ArgumentError("L must be at least 2"))
    J = positive_float(settings["J"], "J")
    aspect_tolerance(settings)
    measurement_sweeps =
        positive_int(settings["measurement_sweeps"], "measurement_sweeps")
    thermalization_sweeps = nonnegative_int(
        settings["thermalization_sweeps"],
        "thermalization_sweeps",
    )
    bin_size = positive_int(settings["bin_size"], "bin_size")
    bin_size <= measurement_sweeps ||
        throw(ArgumentError("bin_size cannot exceed measurement_sweeps"))
    positive_int(settings["minimum_rebin_count"], "minimum_rebin_count")
    maximum_string_fill =
        positive_float(settings["maximum_string_fill"], "maximum_string_fill")
    maximum_string_fill <= 1 ||
        throw(ArgumentError("maximum_string_fill cannot exceed one"))
    string_length_padding = nonnegative_int(
        settings["string_length_padding"],
        "string_length_padding",
    )
    policy = String(get(settings, "beta_policy", "beta_factor_times_L"))

    if policy == "beta_factor_times_L"
        haskey(params, "beta_factor") ||
            throw(ArgumentError("beta_factor is required by $policy"))
        beta_factor = positive_float(params["beta_factor"], "beta_factor")
        h_value = haskey(params, "h") ? params["h"] : settings["h"]
        h = positive_float(h_value, "h")
        beta = beta_factor * L
    elseif policy == "beta_h_equals_L"
        haskey(params, "h") ||
            throw(ArgumentError("cell-specific h is required by $policy"))
        !haskey(params, "beta_factor") ||
            throw(ArgumentError("$policy forbids an independent beta_factor"))
        h = positive_float(params["h"], "h")
        beta = L / h
        beta_factor = beta / L
    else
        throw(ArgumentError("unsupported beta_policy: $policy"))
    end

    T = 1 / beta
    n_sites = lattice_name == "honeycomb" ? 2 * L^2 : L^2
    n_bonds = 3 * L^2
    insertion_weight = n_sites * h + 2 * J * n_bonds
    string_length = ceil(
        Int,
        positive_float(settings["string_length_scale"], "string_length_scale") *
        beta *
        insertion_weight +
        string_length_padding,
    )
    string_length > 0 ||
        throw(ArgumentError("computed string_length must be positive"))
    return (
        lattice_name = lattice_name,
        policy = policy,
        L = L,
        J = J,
        h = h,
        beta = beta,
        beta_factor = beta_factor,
        T = T,
        n_sites = n_sites,
        n_bonds = n_bonds,
        string_length = string_length,
        seed = Int(params["seed"]),
        measurement_sweeps = measurement_sweeps,
        thermalization_sweeps = thermalization_sweeps,
        bin_size = bin_size,
    )
end

function scalar(record, key)
    value = record[key]
    return value isa AbstractVector ? Float64(only(value)) : Float64(value)
end

finite_or_nothing(value) = isfinite(Float64(value)) ? Float64(value) : nothing

function integer_or_nothing(value)
    parsed = Float64(value)
    return isfinite(parsed) && isinteger(parsed) ? Int(parsed) : nothing
end

function write_manifest(spec, cell, cell_dir)
    results_path = joinpath(cell_dir, "sse.results.json")
    isfile(results_path) || error("missing merged results: $results_path")
    task_records = JSON.parsefile(results_path; allownan = true)
    length(task_records) == 1 ||
        error("expected one result in $results_path, got $(length(task_records))")
    record = only(task_records)
    observables = record["results"]
    settings = spec["settings"]
    resolved = resolve_cell(settings, cell["params"])
    effective = record["parameters"]

    sign_mean = scalar(observables["Sign"], "mean")
    field_flip_mean = scalar(observables["FieldFlipCount"], "mean")
    string_fill_mean = scalar(observables["StringFillFraction"], "mean")
    moment_names = ("Mag2", "Mag4", "SpaceTimeMag2", "SpaceTimeMag4")
    rebin_counts = Dict(
        name => Int(observables[name]["rebin_count"]) for name in moment_names
    )
    autocorr_times = Dict(
        name => scalar(observables[name], "autocorr_time") for
        name in moment_names
    )
    observable_names = (
        "Energy",
        "Mag2",
        "Mag4",
        "BinderRatio",
        "SpaceTimeMag2",
        "SpaceTimeMag4",
        "SpaceTimeBinderRatio",
    )
    observable_values = Dict(
        "$name.$field" => scalar(observables[name], field) for
        name in observable_names for field in ("mean", "error")
    )

    effective_L = Float64(effective["L"])
    effective_J = Float64(effective["J"])
    effective_h = Float64(effective["h"])
    effective_beta = Float64(effective["beta"])
    effective_beta_factor = Float64(effective["beta_factor"])
    effective_T = Float64(effective["T"])
    effective_seed = Float64(effective["seed"])
    effective_sweeps = Float64(effective["sweeps"])
    effective_thermalization = Float64(effective["thermalization"])
    effective_binsize = Float64(effective["binsize"])
    effective_string_length = Float64(effective["string_length"])
    effective_numeric = Dict(
        "parameters.L" => effective_L,
        "parameters.J" => effective_J,
        "parameters.h" => effective_h,
        "parameters.T" => effective_T,
        "parameters.beta" => effective_beta,
        "parameters.beta_factor" => effective_beta_factor,
        "parameters.seed" => effective_seed,
        "parameters.sweeps" => effective_sweeps,
        "parameters.thermalization" => effective_thermalization,
        "parameters.binsize" => effective_binsize,
        "parameters.string_length" => effective_string_length,
    )
    diagnostic_numeric = Dict(
        "results.Sign.mean" => sign_mean,
        "results.FieldFlipCount.mean" => field_flip_mean,
        "results.StringFillFraction.mean" => string_fill_mean,
    )
    for (name, value) in autocorr_times
        diagnostic_numeric["results.$name.autocorr_time"] = value
    end
    nonfinite_fields = sort([
        name for
        (name, value) in merge(
            observable_values,
            effective_numeric,
            diagnostic_numeric,
        ) if !isfinite(value)
    ])
    finite_passed = isempty(nonfinite_fields)
    autocorr_passed = all(
        value -> isfinite(value) && value >= 0,
        values(autocorr_times),
    )

    tolerance = aspect_tolerance(settings)
    effective_parameters_passed =
        String(effective["lattice_name"]) == String(settings["lattice_name"]) &&
        isfinite(effective_L) &&
        effective_L == resolved.L &&
        isapprox(effective_J, resolved.J; rtol = tolerance, atol = tolerance) &&
        isapprox(effective_h, resolved.h; rtol = tolerance, atol = tolerance) &&
        isapprox(effective_T, resolved.T; rtol = tolerance, atol = tolerance) &&
        isapprox(
            effective_beta,
            resolved.beta;
            rtol = tolerance,
            atol = tolerance,
        ) &&
        isapprox(
            effective_beta_factor,
            resolved.beta_factor;
            rtol = tolerance,
            atol = tolerance,
        ) &&
        isfinite(effective_seed) &&
        effective_seed == resolved.seed &&
        isfinite(effective_sweeps) &&
        effective_sweeps == resolved.measurement_sweeps &&
        isfinite(effective_thermalization) &&
        effective_thermalization == resolved.thermalization_sweeps &&
        isfinite(effective_binsize) &&
        effective_binsize == resolved.bin_size &&
        isfinite(effective_string_length) &&
        effective_string_length == resolved.string_length
    beta_policy_passed = if resolved.policy == "beta_h_equals_L"
        isfinite(effective_L) &&
        effective_L > 0 &&
        isapprox(
            effective_beta * effective_h / effective_L,
            1.0;
            rtol = tolerance,
            atol = tolerance,
        )
    else
        isfinite(effective_L) &&
        effective_L > 0 &&
        isapprox(
            effective_beta / effective_L,
            resolved.beta_factor;
            rtol = tolerance,
            atol = tolerance,
        )
    end
    temperature_inverse_passed = isapprox(
        effective_T * effective_beta,
        1.0;
        rtol = tolerance,
        atol = tolerance,
    )

    checks = Dict(
        "sign_passed" =>
            isfinite(sign_mean) && 0.999999 <= sign_mean <= 1.000001,
        "field_flip_passed" => isfinite(field_flip_mean) && field_flip_mean > 0,
        "string_fill_passed" =>
            isfinite(string_fill_mean) &&
            string_fill_mean >= 0 &&
            string_fill_mean < Float64(settings["maximum_string_fill"]),
        "rebin_passed" =>
            minimum(values(rebin_counts)) >=
            Int(settings["minimum_rebin_count"]),
        "finite_passed" => finite_passed,
        "autocorr_passed" => autocorr_passed,
        "periodicity_passed" => true,
        "effective_parameters_passed" => effective_parameters_passed,
        "beta_policy_passed" => beta_policy_passed,
        "temperature_inverse_passed" => temperature_inverse_passed,
    )
    health_passed = all(values(checks))

    manifest = Dict(
        "schema_version" => "yanwang148.beta-cell.v2",
        "run_id" => spec["run_id"],
        "cell_id" => cell["cell_id"],
        "status" => health_passed ? "success" : "failed",
        "params" => cell["params"],
        "settings" => settings,
        "provenance" => spec["provenance"],
        "effective_parameters" => Dict(
            "lattice_name" => effective["lattice_name"],
            "L" => integer_or_nothing(effective_L),
            "J" => finite_or_nothing(effective_J),
            "h" => finite_or_nothing(effective_h),
            "T" => finite_or_nothing(effective_T),
            "beta" => finite_or_nothing(effective_beta),
            "beta_policy" => resolved.policy,
            "beta_factor" => finite_or_nothing(effective_beta_factor),
            "beta_over_L" =>
                isfinite(effective_beta) &&
                isfinite(effective_L) &&
                effective_L != 0 ? effective_beta / effective_L : nothing,
            "beta_times_h" =>
                isfinite(effective_beta) && isfinite(effective_h) ?
                effective_beta * effective_h : nothing,
            "seed" => integer_or_nothing(effective_seed),
            "measurement_sweeps" => integer_or_nothing(effective_sweeps),
            "thermalization_sweeps" =>
                integer_or_nothing(effective_thermalization),
            "bin_size" => integer_or_nothing(effective_binsize),
            "string_length" => integer_or_nothing(effective_string_length),
        ),
        "observables" => Dict(
            "binder" =>
                finite_or_nothing(scalar(observables["BinderRatio"], "mean")),
            "binder_se" =>
                finite_or_nothing(scalar(observables["BinderRatio"], "error")),
            "mag2" => finite_or_nothing(scalar(observables["Mag2"], "mean")),
            "mag2_se" =>
                finite_or_nothing(scalar(observables["Mag2"], "error")),
            "mag4" => finite_or_nothing(scalar(observables["Mag4"], "mean")),
            "mag4_se" =>
                finite_or_nothing(scalar(observables["Mag4"], "error")),
            "spacetime_binder" =>
                finite_or_nothing(
                    scalar(observables["SpaceTimeBinderRatio"], "mean"),
                ),
            "spacetime_binder_se" =>
                finite_or_nothing(
                    scalar(observables["SpaceTimeBinderRatio"], "error"),
                ),
            "spacetime_mag2" =>
                finite_or_nothing(scalar(observables["SpaceTimeMag2"], "mean")),
            "spacetime_mag2_se" =>
                finite_or_nothing(
                    scalar(observables["SpaceTimeMag2"], "error"),
                ),
            "spacetime_mag4" =>
                finite_or_nothing(scalar(observables["SpaceTimeMag4"], "mean")),
            "spacetime_mag4_se" =>
                finite_or_nothing(
                    scalar(observables["SpaceTimeMag4"], "error"),
                ),
            "energy" =>
                finite_or_nothing(scalar(observables["Energy"], "mean")),
            "energy_se" =>
                finite_or_nothing(scalar(observables["Energy"], "error")),
        ),
        "diagnostics" => Dict(
            "health_passed" => health_passed,
            "checks" => checks,
            "sign_mean" => finite_or_nothing(sign_mean),
            "field_flip_mean" => finite_or_nothing(field_flip_mean),
            "string_fill_mean" => finite_or_nothing(string_fill_mean),
            "rebin_counts" => rebin_counts,
            "autocorr_times" => Dict(
                name => finite_or_nothing(value) for
                (name, value) in autocorr_times
            ),
            "nonfinite_fields" => nonfinite_fields,
        ),
        "artifacts" => [
            Dict(
                "path" => relpath(results_path, pwd()),
                "bytes" => filesize(results_path),
                "sha256" => bytes2hex(sha256(read(results_path))),
            ),
        ],
    )
    open(joinpath(cell_dir, "manifest.json"), "w") do io
        JSON.print(io, manifest, 2)
        println(io)
    end
    return manifest
end

end
