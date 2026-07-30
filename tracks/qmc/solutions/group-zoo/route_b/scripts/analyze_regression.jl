using RouteBWorm
using JSON
using SHA
using Statistics

function parse_options(args)
    values = Dict{String,String}()
    index = 1
    while index <= length(args)
        startswith(args[index], "--") || error("arguments must use --key value")
        index < length(args) || error("missing value for $(args[index])")
        values[args[index][3:end]] = args[index + 1]
        index += 2
    end
    for name in ("tasks", "results", "report", "stage")
        haskey(values, name) || error("--$name is required")
    end
    return values
end

function system_metrics(payloads)
    isempty(payloads) && error("calibration system has no payloads")
    raw_wrapping = Float64[]
    total_ess = 0.0
    total_seconds = 0.0
    accepted = Dict{String,Int}()
    g_visits = 0
    z_visits = 0
    for payload in payloads
        payload["status"] == "complete" || error("partial calibration payload")
        append!(raw_wrapping, Float64[bin["R_down"] for bin in payload["raw_bins"]])
        total_ess += Float64(payload["summary"]["R_down_ess"])
        total_seconds += Float64(payload["elapsed_seconds"])
        for (family, count) in payload["accepted"]
            accepted[family] = get(accepted, family, 0) + Int(count)
        end
        g_visits += sum(Int(bin["g_visits"]) for bin in payload["raw_bins"])
        z_visits += sum(Int(bin["z_visits"]) for bin in payload["raw_bins"])
    end
    required_families = (
        "CreateDefects", "AnnihilateDefects", "MoveDefect", "InsertKink", "DeleteKink",
    )
    reasons = String[]
    minimum(raw_wrapping) < maximum(raw_wrapping) || push!(reasons, "no_wrapping_variation")
    g_visits > 0 || push!(reasons, "no_green_sector")
    z_visits > 0 || push!(reasons, "no_closed_sector")
    for family in required_families
        get(accepted, family, 0) > 0 || push!(reasons, "no_accepted_$family")
    end
    return (
        ergodic=isempty(reasons),
        rejection_reasons=reasons,
        wrapping_mean=mean(raw_wrapping),
        wrapping_min=minimum(raw_wrapping),
        wrapping_max=maximum(raw_wrapping),
        ess=total_ess,
        elapsed_seconds=total_seconds,
        ess_per_second=total_ess / total_seconds,
        g_visits=g_visits,
        z_visits=z_visits,
        accepted=accepted,
    )
end

function calibration_report(task_root, result_root, task_names)
    groups = Dict{NTuple{3,Float64},Dict{Symbol,Vector{Any}}}()
    task_hashes = Dict{NTuple{3,Float64},Vector{String}}()
    for task_name in task_names
        task = parse_task(read(joinpath(task_root, task_name), String))
        payload = JSON.parsefile(joinpath(result_root, task_name))
        payload["task_hash"] == task_hash(task) || error("calibration task hash mismatch")
        multipliers = task.tau_multipliers
        systems = get!(groups, multipliers, Dict(:chain => Any[], :square => Any[]))
        push!(systems[task.lattice], payload)
        push!(get!(task_hashes, multipliers, String[]), payload["task_hash"])
    end
    candidates = NamedTuple[]
    for multipliers in sort!(collect(keys(groups)))
        chain = system_metrics(groups[multipliers][:chain])
        square = system_metrics(groups[multipliers][:square])
        push!(candidates, (
            multipliers=multipliers,
            ess_per_second=min(chain.ess_per_second, square.ess_per_second),
            ergodic=chain.ergodic && square.ergodic,
            chain=chain,
            square=square,
            task_hashes=sort!(task_hashes[multipliers]),
        ))
    end
    selected = select_calibration(candidates)
    return (
        schema=1,
        stage="regression_calibration",
        status="pass",
        production_authorized=false,
        manifest_sha256=bytes2hex(SHA.sha256(read(joinpath(task_root, "manifest.json")))),
        candidate_count=length(candidates),
        ergodic_count=count(candidate -> candidate.ergodic, candidates),
        selected=(
            multipliers=selected.multipliers,
            ess_per_second=selected.ess_per_second,
            chain=selected.chain,
            square=selected.square,
        ),
        candidates=candidates,
    )
end

function fit_system(rows, specifications; reference, tolerance, sigma_multiplier, seed)
    windows = [fit_window_record(rows; specification...) for specification in specifications]
    successful = [window for window in windows if window.status == "pass"]
    if isempty(successful)
        return (
            status="fail", windows=windows, bootstrap=nothing,
            gate=(status="fail", reasons=["no_successful_fit_window"]),
        )
    end
    primary_specification = first(specifications)
    bootstrap = try
        bootstrap_scaling(rows; replicas=400, seed=seed, primary_specification...)
    catch error
        error isa ArgumentError || rethrow()
        nothing
    end
    primary = first(windows)
    bootstrap === nothing && return (
        status="fail", windows=windows, bootstrap=nothing,
        gate=(status="fail", reasons=["primary_bootstrap_failed"]),
    )
    primary.status == "pass" || return (
        status="fail", windows=windows, bootstrap=bootstrap,
        gate=(status="fail", reasons=["primary_fit_window_failed"]),
    )
    declared_systematic = maximum(abs(window.hc - primary.hc) for window in successful)
    gate_windows = copy(windows)
    gate_windows[1] = merge(primary, (stderr_hc=bootstrap.stderr_hc,))
    gate = evaluate_regression_gate(
        gate_windows;
        reference=reference,
        absolute_tolerance=tolerance,
        sigma_multiplier=sigma_multiplier,
        declared_systematic=declared_systematic,
    )
    return (
        status=gate.status,
        windows=windows,
        bootstrap=bootstrap,
        gate=gate,
    )
end

function universal_report(task_root, result_root, task_names)
    rows = Dict(:chain => NamedTuple[], :square => NamedTuple[])
    task_hashes = String[]
    total_seconds = 0.0
    for task_name in task_names
        task = parse_task(read(joinpath(task_root, task_name), String))
        payload = JSON.parsefile(joinpath(result_root, task_name))
        verify_result_payload(task, payload)
        summary = payload["summary"]
        push!(rows[task.lattice], (
            L=task.L,
            h=task.h,
            replica=Int(task.seed % UInt64(100)),
            value=Float64(summary["R_down"]),
            stderr=Float64(summary["R_down_stderr"]),
        ))
        push!(task_hashes, payload["task_hash"])
        total_seconds += Float64(payload["elapsed_seconds"])
    end
    chain_specifications = [
        (Lmin=Lmin, corrections=corrections, yt=1.0, yi=-1.0, hc_bounds=(0.98, 1.02))
        for (Lmin, corrections) in ((12, 1), (16, 1), (12, 0), (16, 0))
    ]
    square_specifications = [
        (Lmin=Lmin, corrections=corrections, yt=1.5873, yi=-0.83,
         hc_bounds=(3.02, 3.07))
        for (Lmin, corrections) in ((8, 1), (10, 1), (12, 1), (8, 0), (10, 0), (12, 0))
    ]
    chain = fit_system(
        rows[:chain], chain_specifications;
        reference=1.0, tolerance=2e-4, sigma_multiplier=0.0, seed=1481101,
    )
    square = fit_system(
        rows[:square], square_specifications;
        reference=3.044330, tolerance=5e-5, sigma_multiplier=3.0, seed=1481102,
    )
    status = chain.status == "pass" && square.status == "pass" ? "pass" : "fail"
    return (
        schema=1,
        stage="universal_regression",
        status=status,
        production_authorized=false,
        manifest_sha256=bytes2hex(SHA.sha256(read(joinpath(task_root, "manifest.json")))),
        task_count=length(task_names),
        task_hashes=sort!(task_hashes),
        accumulated_task_seconds=total_seconds,
        chain=chain,
        square=square,
    )
end

options = parse_options(ARGS)
stage = options["stage"]
stage in ("calibration", "regression") || error("--stage must be calibration or regression")
task_root = abspath(options["tasks"])
result_root = abspath(options["results"])
manifest = JSON.parsefile(joinpath(task_root, "manifest.json"))
expected_manifest_stage = stage == "calibration" ? "regression_calibration" : "universal_regression"
manifest["stage"] == expected_manifest_stage || error("wrong manifest stage")
task_names = filter(!isempty, readlines(joinpath(task_root, "task_paths.txt")))
report = stage == "calibration" ?
    calibration_report(task_root, result_root, task_names) :
    universal_report(task_root, result_root, task_names)

report_path = abspath(options["report"])
mkpath(dirname(report_path))
temporary = report_path * ".tmp-" * string(getpid())
open(temporary, "w") do io
    write(io, JSON.json(report))
end
mv(temporary, report_path; force=true)
println("Route B $stage analysis: $(report.status)")
