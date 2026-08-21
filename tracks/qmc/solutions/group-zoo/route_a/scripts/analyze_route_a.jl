using JSON
using TOML

include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
using .Challenge148

const _ANALYSIS_WINDOW_FIELDS = Set((
    "models",
    "L_min",
    "yt_modes",
    "yt_fixed",
    "yt_free_bounds",
    "yi_fixed",
    "minimum_degrees_of_freedom",
    "maximum_reduced_chi_square",
    "bootstrap_seed",
    "bootstrap_draws",
    "reweight_ess_fraction",
    "status",
))

function _frozen_windows(path::AbstractString; reader=read)
    islink(path) && throw(ArgumentError("analysis windows must not be a symlink"))
    isfile(path) || throw(ArgumentError("analysis windows must be a regular file"))
    snapshot = try
        Challenge148._parsed_content_snapshot(
            path, bytes -> TOML.parse(String(bytes)); reader=reader)
    catch error
        throw(ArgumentError("could not parse analysis windows: $(sprint(showerror, error))"))
    end
    windows = snapshot.value
    Set(string.(keys(windows))) == _ANALYSIS_WINDOW_FIELDS ||
        throw(ArgumentError("analysis windows have missing or unknown fields"))
    windows["models"] == ["M1", "M2", "M3"] ||
        throw(ArgumentError("analysis models do not match the frozen families"))
    windows["L_min"] == [8, 12, 16, 24] ||
        throw(ArgumentError("analysis size windows do not match the frozen windows"))
    windows["yt_modes"] == ["fixed", "free"] ||
        throw(ArgumentError("analysis yt modes do not match the frozen modes"))
    windows["yt_fixed"] == 1.5868 || throw(ArgumentError("analysis fixed yt is not frozen"))
    windows["yt_free_bounds"] == [1.50, 1.67] ||
        throw(ArgumentError("analysis free-yt bounds are not frozen"))
    windows["yi_fixed"] == -0.821 || throw(ArgumentError("analysis fixed yi is not frozen"))
    windows["minimum_degrees_of_freedom"] == 2 ||
        throw(ArgumentError("analysis dof gate is not frozen"))
    windows["maximum_reduced_chi_square"] == 2.0 ||
        throw(ArgumentError("analysis chi-square gate is not frozen"))
    windows["bootstrap_seed"] == 148900 ||
        throw(ArgumentError("analysis bootstrap seed is not frozen"))
    windows["bootstrap_draws"] == 2000 ||
        throw(ArgumentError("analysis bootstrap draw count is not frozen"))
    windows["reweight_ess_fraction"] == 0.30 ||
        throw(ArgumentError("analysis reweighting gate is not frozen"))
    windows["status"] == Challenge148.ROUTE_A_PRELIMINARY_STATUS ||
        throw(ArgumentError("analysis status must enforce the exact preliminary label"))
    return snapshot
end

_json_number(value::Real) = isfinite(value) ? value : nothing

function _fit_record(fit::BinderFitResult, lattice::Symbol)
    return (
        lattice=String(lattice),
        model=String(fit.model),
        L_min=fit.L_min,
        yt_mode=String(fit.yt_mode),
        parameter_order=String.(collect(fit.parameter_names)),
        parameters=Dict{String,Any}(
            String(name) => _json_number(getproperty(fit.parameters, name)) for name in fit.parameter_names),
        parameter_bounds=fit.yt_mode === :free ? Dict("yt" => collect(Challenge148.FSS_YT_BOUNDS)) : Dict(),
        covariance=[[_json_number(value) for value in row] for row in eachrow(fit.covariance)],
        chi2=_json_number(fit.chi2),
        dof=fit.dof,
        reduced_chi2=_json_number(fit.reduced_chi2),
        converged=fit.converged,
        accepted=fit.accepted,
        rejection_reasons=fit.rejection_reasons,
        nrows=fit.nrows,
        sizes=fit.sizes,
    )
end

function _analysis_records(
    report,
    data::CombinedBinderData,
    window_config_sha256::String;
    analysis_mode::String,
    production_eligible::Bool,
    fit_windows_filename::String,
)
    windows = [
        _fit_record(fit, index <= 24 ? :triangle : :honeycomb)
        for (index, fit) in enumerate(report.fit_windows)
    ]
    accepted = [window for window in windows if window.accepted]
    inputs = (
        campaign_id=data.campaign_id,
        campaign_checksum=data.campaign_checksum,
        git_commit=data.git_commit,
        julia_version=data.julia_version,
        julia_manifest_sha256=data.julia_manifest_sha256,
        algorithm=data.algorithm,
        observable_schema_version=data.observable_schema_version,
        data_content_sha256=data.content_sha256,
        window_config_content_sha256=window_config_sha256,
    )
    bootstrap = (seed=report.bootstrap.seed, draws=report.bootstrap.draws, mode=analysis_mode)
    preliminary = (
        schema_version=1,
        kind="route_a_preliminary_analysis",
        status=Challenge148.ROUTE_A_PRELIMINARY_STATUS,
        analysis_mode=analysis_mode,
        production_eligible=production_eligible,
        inputs=inputs,
        R=report.R,
        Delta=report.Delta,
        critical_points=report.critical_points,
        errors=report.errors,
        bootstrap=bootstrap,
        accepted_window_count=length(accepted),
        attempted_window_count=length(windows),
        accepted_windows=[(
            lattice=window.lattice,
            model=window.model,
            L_min=window.L_min,
            yt_mode=window.yt_mode,
        ) for window in accepted],
        fit_windows_file=fit_windows_filename,
    )
    table = (
        schema_version=1,
        kind="route_a_fit_windows",
        status=Challenge148.ROUTE_A_PRELIMINARY_STATUS,
        analysis_mode=analysis_mode,
        production_eligible=production_eligible,
        inputs=inputs,
        bootstrap=bootstrap,
        fit_windows=windows,
    )
    return preliminary, table
end

function _write_route_a_analysis(
    data_path::AbstractString,
    windows_path::AbstractString,
    output_path::AbstractString;
    draws::Int,
    analysis_mode::String,
    production_eligible::Bool,
    preliminary_filename::String,
    windows_filename::String,
)
    window_snapshot = _frozen_windows(windows_path)
    windows = window_snapshot.value
    islink(output_path) && throw(ArgumentError("analysis output must not be a symlink"))
    isdir(output_path) || throw(ArgumentError("analysis output must be an existing directory"))
    draws > 1 || throw(ArgumentError("analysis bootstrap draws must exceed one"))
    if production_eligible
        draws == windows["bootstrap_draws"] && analysis_mode == "frozen_production" &&
            preliminary_filename == "route_a_preliminary.json" && windows_filename == "fit_windows.json" ||
            throw(ArgumentError("frozen production artifacts require the frozen mode, names, and 2,000 draws"))
    else
        analysis_mode == "test_nonproduction" && occursin("TEST_ONLY", preliminary_filename) &&
            occursin("TEST_ONLY", windows_filename) ||
            throw(ArgumentError("non-production analysis requires TEST_ONLY mode and filenames"))
    end
    data = read_combined_binder_data(data_path)
    report = analyze_route_a_replicas(
        data.records; seed=windows["bootstrap_seed"], draws=draws)
    report.status == Challenge148.ROUTE_A_PRELIMINARY_STATUS ||
        throw(ArgumentError("analysis did not produce the required preliminary status"))
    preliminary_record, window_record = _analysis_records(
        report, data, window_snapshot.content_sha256;
        analysis_mode, production_eligible, fit_windows_filename=windows_filename)
    preliminary_path = joinpath(output_path, preliminary_filename)
    fit_windows_path = joinpath(output_path, windows_filename)
    atomic_write_json(fit_windows_path, window_record)
    atomic_write_json(preliminary_path, preliminary_record)
    return (preliminary=preliminary_path, fit_windows=fit_windows_path)
end

"""Run the frozen 2,000-draw analysis and write production-named preliminary artifacts."""
function write_route_a_analysis(
    data_path::AbstractString,
    windows_path::AbstractString,
    output_path::AbstractString,
)
    return _write_route_a_analysis(
        data_path, windows_path, output_path;
        draws=2000,
        analysis_mode="frozen_production",
        production_eligible=true,
        preliminary_filename="route_a_preliminary.json",
        windows_filename="fit_windows.json",
    )
end


"""Test-only small-draw writer; filenames and schema are explicitly non-production."""
function _write_route_a_test_analysis(
    data_path::AbstractString,
    windows_path::AbstractString,
    output_path::AbstractString;
    draws::Integer,
)
    return _write_route_a_analysis(
        data_path, windows_path, output_path;
        draws=Int(draws),
        analysis_mode="test_nonproduction",
        production_eligible=false,
        preliminary_filename="route_a_preliminary.TEST_ONLY.json",
        windows_filename="fit_windows.TEST_ONLY.json",
    )
end

"""Parse exactly `--data PATH --windows PATH --output DIR`; all other arguments are rejected."""
function parse_analysis_args(arguments::Vector{String})
    length(arguments) == 6 ||
        throw(ArgumentError("usage: analyze_route_a.jl --data PATH --windows PATH --output DIR"))
    arguments[1] == "--data" && arguments[3] == "--windows" && arguments[5] == "--output" ||
        throw(ArgumentError("usage: analyze_route_a.jl --data PATH --windows PATH --output DIR"))
    all(!isempty, (arguments[2], arguments[4], arguments[6])) ||
        throw(ArgumentError("analysis paths must be nonempty"))
    return (data_path=arguments[2], windows_path=arguments[4], output_dir=arguments[6])
end

function _main()
    arguments = parse_analysis_args(copy(ARGS))
    write_route_a_analysis(arguments.data_path, arguments.windows_path, arguments.output_dir)
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    try
        _main()
    catch error
        Base.display_error(stderr, catch_backtrace())
        exit(1)
    end
end
