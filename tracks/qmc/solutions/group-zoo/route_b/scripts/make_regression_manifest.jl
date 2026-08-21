using RouteBWorm
using JSON
using SHA
using TOML

function parse_options(args)
    values = Dict{String,String}()
    index = 1
    while index <= length(args)
        startswith(args[index], "--") || error("arguments must use --key value")
        index < length(args) || error("missing value for $(args[index])")
        values[args[index][3:end]] = args[index + 1]
        index += 2
    end
for name in ("config", "output", "stage")
        haskey(values, name) || error("--$name is required")
    end
    return values
end

options = parse_options(ARGS)
stage = options["stage"]
stage in ("calibration", "regression") ||
    error("--stage must be calibration or regression")
config_path = abspath(options["config"])
config = TOML.parsefile(config_path)
Int(config["schema"]) == 1 || error("unsupported regression config schema")
config["production_authorized"] == false || error("regression config must forbid production")
section = copy(config[stage])
section["J"] = config["J"]
tasks = if stage == "calibration"
    make_regression_calibration_tasks(section)
else
    report_path = get(ENV, "ROUTE_B_CALIBRATION_REPORT", "")
    isempty(report_path) && error("ROUTE_B_CALIBRATION_REPORT is required for regression")
    isfile(report_path) || error("calibration report does not exist")
    report_sha256 = bytes2hex(SHA.sha256(read(report_path)))
    report_sha256 == section["calibration_report_sha256"] ||
        error("calibration report SHA-256 mismatch")
    report = JSON.parsefile(report_path)
    report["status"] == "pass" || error("calibration report did not pass")
    selected = Tuple(Float64.(report["selected"]["multipliers"]))
    selected == Tuple(Float64.(section["selected_tau_multipliers"])) ||
        error("configured multipliers do not match calibration report")
    make_universal_regression_tasks(section)
end

output = abspath(options["output"])
if isdir(output) && !isempty(readdir(output))
    error("regression task output directory is not empty")
end
mkpath(output)
records = NamedTuple[]
task_paths = String[]
for (index, task) in enumerate(tasks)
    hash = task_hash(task)
    prefix = stage == "calibration" ? "rb-cal" : "rb-reg"
    name = "$prefix-$(task.lattice)-$(lpad(index, 4, '0'))-$(hash[1:8]).json"
    open(joinpath(output, name), "w") do io
        write(io, canonical_task_json(task))
    end
    push!(task_paths, name)
    push!(records, (
        path=name,
        task_hash=hash,
        lattice=String(task.lattice),
        tau_multipliers=collect(task.tau_multipliers),
        seed=string(task.seed),
    ))
end
open(joinpath(output, "task_paths.txt"), "w") do io
    foreach(path -> println(io, path), task_paths)
end
manifest = (
    schema=1,
    stage=stage == "calibration" ? "regression_calibration" : "universal_regression",
    production_authorized=false,
    config_sha256=bytes2hex(SHA.sha256(read(config_path))),
    tasks=records,
)
open(joinpath(output, "manifest.json"), "w") do io
    write(io, JSON.json(manifest))
end
println("wrote $(length(tasks)) Route B $stage tasks to $output")
