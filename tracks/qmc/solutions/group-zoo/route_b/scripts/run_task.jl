using RouteBWorm
using JSON
using SHA

function parse_args(args)
    values = Dict{String,String}()
    index = 1
    while index <= length(args)
        startswith(args[index], "--") || error("arguments must use --key value")
        index < length(args) || error("missing value for $(args[index])")
        values[args[index][3:end]] = args[index + 1]
        index += 2
    end
    haskey(values, "task") || error("--task is required")
    haskey(values, "output") || error("--output is required")
    return values
end

options = parse_args(ARGS)
task = parse_task(read(options["task"], String))
checkpoint = get(options, "checkpoint", options["output"] * ".checkpoint")
resume = get(options, "resume", "false") == "true"
stop_after = haskey(options, "stop-after-bins") ? parse(Int, options["stop-after-bins"]) : nothing
result = run_task(task; checkpoint_path=checkpoint, resume=resume, stop_after_bins=stop_after)
git_commit = get(ENV, "ROUTE_B_RELEASE_COMMIT", "")
manifest_path = joinpath(dirname(abspath(options["task"])), "manifest.json")
isfile(manifest_path) && !islink(manifest_path) || error("task manifest is unavailable")
payload = make_result_payload(
    task,
    result;
    git_commit=git_commit,
    manifest_sha256=bytes2hex(SHA.sha256(read(manifest_path))),
)
temporary = options["output"] * ".tmp-" * string(getpid())
open(temporary, "w") do io
    write(io, JSON.json(payload))
end
mv(temporary, options["output"]; force=true)
