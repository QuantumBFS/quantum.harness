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
    for name in ("tasks", "results", "report")
        haskey(values, name) || error("--$name is required")
    end
    values["config"] = get(values, "config", "route_b/config/ed_validation.toml")
    return values
end

options = parse_options(ARGS)
task_root = abspath(options["tasks"])
result_root = abspath(options["results"])
config_path = abspath(options["config"])
config = TOML.parsefile(config_path)
reference_path = abspath(dirname(config_path), "..", "..", config["reference"])
bytes2hex(SHA.sha256(read(reference_path))) == config["reference_sha256"] ||
    error("ED reference checksum mismatch")
references = JSON.parsefile(reference_path)
replicas = Int(config["replicas"])
task_names = filter(!isempty, readlines(joinpath(task_root, "task_paths.txt")))
length(task_names) == length(references) * replicas ||
    error("ED task count does not match rows times replicas")

row_reports = NamedTuple[]
for (row_index, reference) in enumerate(references)
    payloads = Any[]
    hashes = String[]
    first = (row_index - 1) * replicas + 1
    for task_index in first:(first + replicas - 1)
        task_name = task_names[task_index]
        task = parse_task(read(joinpath(task_root, task_name), String))
        task.lattice == Symbol(reference["lattice"]) || error("ED task lattice mismatch")
        task.L == Int(reference["L"]) || error("ED task size mismatch")
        task.beta == Float64(reference["beta"]) || error("ED task beta mismatch")
        payload = JSON.parsefile(joinpath(result_root, task_name))
        payload["task_hash"] == task_hash(task) || error("ED result task hash mismatch")
        push!(payloads, payload)
        push!(hashes, payload["task_hash"])
    end
    summary = summarize_result_payloads(payloads)
    comparison = compare_ed(summary, reference)
    push!(row_reports, (
        lattice=reference["lattice"],
        L=reference["L"],
        c=reference["c"],
        beta=reference["beta"],
        replicas=replicas,
        task_hashes=hashes,
        qmc=summary,
        reference=(
            energy=reference["energy"],
            mx=reference["mx"],
            bond=reference["bond"],
            worm_return=reference["worm_return"],
        ),
        status=String(comparison.status),
        production_eligible=comparison.production_eligible,
        failures=comparison.failures,
        absolute_differences=comparison.comparisons,
    ))
end

passed = all(row.status == "pass" for row in row_reports)
report = (
    schema=1,
    purpose="route_b_ed_validation",
    status=passed ? "pass" : "fail",
    production_eligible=passed,
    production_authorized=false,
    reference_sha256=config["reference_sha256"],
    rows=row_reports,
)
report_path = abspath(options["report"])
mkpath(dirname(report_path))
temporary = report_path * ".tmp-" * string(getpid())
open(temporary, "w") do io
    write(io, JSON.json(report))
end
mv(temporary, report_path; force=true)
println("Route B ED gate: $(report.status) ($(length(row_reports)) rows)")
passed || exit(1)
