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
    haskey(values, "config") || error("--config is required")
    haskey(values, "output") || error("--output is required")
    return values
end

options = parse_options(ARGS)
config_path = abspath(options["config"])
config = TOML.parsefile(config_path)
reference_path = abspath(dirname(config_path), "..", "..", config["reference"])
bytes2hex(SHA.sha256(read(reference_path))) == config["reference_sha256"] ||
    error("ED reference checksum mismatch")
rows = JSON.parsefile(reference_path)
tasks = make_ed_validation_tasks(config, rows)
output = abspath(options["output"])
if isdir(output) && !isempty(readdir(output))
    error("ED task output directory is not empty")
end
mkpath(output)

paths = String[]
records = NamedTuple[]
replicas = Int(config["replicas"])
for (index, task) in enumerate(tasks)
    row = div(index - 1, replicas) + 1
    replica = mod(index - 1, replicas) + 1
    hash = task_hash(task)
    name = "rb-ed-$(task.lattice)-L$(lpad(task.L, 4, '0'))-c$(rows[row]["c"])-r$(lpad(replica, 3, '0'))-$(hash[1:8]).json"
    path = joinpath(output, name)
    open(path, "w") do io
        write(io, canonical_task_json(task))
    end
    push!(paths, name)
    push!(records, (path=name, task_hash=hash, row=row, replica=replica))
end
open(joinpath(output, "task_paths.txt"), "w") do io
    foreach(path -> println(io, path), paths)
end
manifest = (
    schema=1,
    purpose="ed_validation",
    production_authorized=false,
    config_sha256=bytes2hex(SHA.sha256(read(config_path))),
    reference_sha256=config["reference_sha256"],
    tasks=records,
)
open(joinpath(output, "manifest.json"), "w") do io
    write(io, JSON.json(manifest))
end
println("wrote $(length(tasks)) ED validation tasks to $output")
